//+------------------------------------------------------------------+
//|                                EntryStrategy_Bridge_5558.mq5    |
//|                    High-Speed Tick & Bar Bridge for Port 5558    |
//+------------------------------------------------------------------+
#property copyright "Entry Strategy Matrix"
#property link      ""
#property version   "1.02"
#property description "Streams MT5 real-time ticks to Entry Strategy App on Port 5558"

input string InpHost = "127.0.0.1";
input int    InpPort = 5558;

int  client_socket = INVALID_HANDLE;
bool meta_sent = false;
bool is_connecting = false;
datetime last_retry_time = 0;
datetime last_m1_bar_time = 0;
datetime last_m5_bar_time = 0;

int OnInit()
{
    Print("[EntryStrategy] Initializing Bridge on port ", InpPort, " for symbol ", _Symbol, "...");
    ConnectSocket();
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
    if(client_socket != INVALID_HANDLE)
    {
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
        Print("[EntryStrategy] Socket closed cleanly.");
    }
}

bool ConnectSocket()
{
    if(is_connecting) return false;
    is_connecting = true;

    if(client_socket != INVALID_HANDLE)
    {
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
    }
    
    client_socket = SocketCreate();
    if(client_socket == INVALID_HANDLE)
    {
        Print("[EntryStrategy] Failed to create socket. Error: ", GetLastError());
        is_connecting = false;
        return false;
    }
    
    if(SocketConnect(client_socket, InpHost, InpPort, 1000))
    {
        Print("[EntryStrategy] Connected successfully to port ", InpPort, " (Symbol: ", _Symbol, ")");
        meta_sent = false;
        is_connecting = false;
        SendMeta();
        return true;
    }
    else
    {
        // App might not be running yet, will retry on subsequent ticks
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
        is_connecting = false;
        return false;
    }
}

bool SendRawString(string data)
{
    if(client_socket == INVALID_HANDLE)
    {
        datetime now = TimeCurrent();
        if(now - last_retry_time < 3) return false;
        last_retry_time = now;
        if(!ConnectSocket()) return false;
    }

    uchar buffer[];
    int len = StringLen(data);
    if(len <= 0) return true;

    StringToCharArray(data, buffer, 0, len);
    // Crucial: send exactly 'len' bytes without the trailing null byte
    int sent = SocketSend(client_socket, buffer, len);
    if(sent < 0)
    {
        Print("[EntryStrategy] Socket send failed. Error: ", GetLastError(), ". Reconnecting...");
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
        return false;
    }
    return true;
}

void SendHistoricalBars()
{
    // 1. Stream 100 historical M1 candles
    MqlRates rates_m1[];
    ArraySetAsSeries(rates_m1, false);
    int copied_m1 = CopyRates(_Symbol, PERIOD_M1, 1, 100, rates_m1);
    if(copied_m1 > 0)
    {
        Print("[EntryStrategy] Streaming ", copied_m1, " historical M1 candles to port ", InpPort, "...");
        for(int i = 0; i < copied_m1; i++)
        {
            string barLine = StringFormat("#BAR:M1,%I64d,%.5f,%.5f,%.5f,%.5f,%.0f,%.0f,%.1f\n",
                (long)rates_m1[i].time,
                rates_m1[i].open,
                rates_m1[i].high,
                rates_m1[i].low,
                rates_m1[i].close,
                (double)rates_m1[i].tick_volume,
                (double)rates_m1[i].real_volume,
                (double)rates_m1[i].spread
            );
            SendRawString(barLine);
        }
        last_m1_bar_time = iTime(_Symbol, PERIOD_M1, 0);
    }

    // 2. Stream 100 historical M5 candles
    MqlRates rates_m5[];
    ArraySetAsSeries(rates_m5, false);
    int copied_m5 = CopyRates(_Symbol, PERIOD_M5, 1, 100, rates_m5);
    if(copied_m5 > 0)
    {
        Print("[EntryStrategy] Streaming ", copied_m5, " historical M5 candles to port ", InpPort, "...");
        for(int i = 0; i < copied_m5; i++)
        {
            string barLine = StringFormat("#BAR:M5,%I64d,%.5f,%.5f,%.5f,%.5f,%.0f,%.0f,%.1f\n",
                (long)rates_m5[i].time,
                rates_m5[i].open,
                rates_m5[i].high,
                rates_m5[i].low,
                rates_m5[i].close,
                (double)rates_m5[i].tick_volume,
                (double)rates_m5[i].real_volume,
                (double)rates_m5[i].spread
            );
            SendRawString(barLine);
        }
        last_m5_bar_time = iTime(_Symbol, PERIOD_M5, 0);
    }
}

void SendMeta()
{
    string symLine = StringFormat("#SYMBOL:%s\n", _Symbol);
    SendRawString(symLine);
    
    int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    string metaLine = StringFormat("#META:%d,%f\n", digits, point);
    SendRawString(metaLine);
    
    SendHistoricalBars();
    meta_sent = true;
}

void OnTick()
{
    MqlTick tick;
    if(!SymbolInfoTick(_Symbol, tick)) return;

    if(!meta_sent || client_socket == INVALID_HANDLE)
    {
        datetime now = TimeCurrent();
        if(now - last_retry_time >= 3)
        {
            last_retry_time = now;
            ConnectSocket();
        }
        if(client_socket == INVALID_HANDLE) return;
    }

    // Check if a new M1 bar closed
    datetime cur_m1_time = iTime(_Symbol, PERIOD_M1, 0);
    if(last_m1_bar_time == 0)
    {
        last_m1_bar_time = cur_m1_time;
    }
    else if(cur_m1_time > last_m1_bar_time)
    {
        last_m1_bar_time = cur_m1_time;
        MqlRates closed_m1[];
        ArraySetAsSeries(closed_m1, true);
        if(CopyRates(_Symbol, PERIOD_M1, 1, 1, closed_m1) > 0)
        {
            string barLine = StringFormat("#BAR:M1,%I64d,%.5f,%.5f,%.5f,%.5f,%.0f,%.0f,%.1f\n",
                (long)closed_m1[0].time,
                closed_m1[0].open,
                closed_m1[0].high,
                closed_m1[0].low,
                closed_m1[0].close,
                (double)closed_m1[0].tick_volume,
                (double)closed_m1[0].real_volume,
                (double)closed_m1[0].spread
            );
            SendRawString(barLine);
        }
    }

    // Check if a new M5 bar closed
    datetime cur_m5_time = iTime(_Symbol, PERIOD_M5, 0);
    if(last_m5_bar_time == 0)
    {
        last_m5_bar_time = cur_m5_time;
    }
    else if(cur_m5_time > last_m5_bar_time)
    {
        last_m5_bar_time = cur_m5_time;
        MqlRates closed_m5[];
        ArraySetAsSeries(closed_m5, true);
        if(CopyRates(_Symbol, PERIOD_M5, 1, 1, closed_m5) > 0)
        {
            string barLine = StringFormat("#BAR:M5,%I64d,%.5f,%.5f,%.5f,%.5f,%.0f,%.0f,%.1f\n",
                (long)closed_m5[0].time,
                closed_m5[0].open,
                closed_m5[0].high,
                closed_m5[0].low,
                closed_m5[0].close,
                (double)closed_m5[0].tick_volume,
                (double)closed_m5[0].real_volume,
                (double)closed_m5[0].spread
            );
            SendRawString(barLine);
        }
    }

    // Send tick for real-time bid/ask/price readout
    long ts_msc = tick.time_msc;
    if(ts_msc <= 0)
    {
        ts_msc = (long)tick.time * 1000 + (GetMicrosecondCount() % 1000000) / 1000;
    }

    double vol = tick.volume_real > 0 ? tick.volume_real : (double)tick.volume;
    if(vol <= 0) vol = 1.0;

    string tickLine = StringFormat("%I64d,%.5f,%.5f,%.5f,%.2f,%d\n",
        ts_msc,
        tick.bid,
        tick.ask,
        tick.last,
        vol,
        tick.flags
    );

    SendRawString(tickLine);
}
