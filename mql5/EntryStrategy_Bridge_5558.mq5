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

void SendMeta()
{
    string symLine = StringFormat("#SYMBOL:%s\n", _Symbol);
    SendRawString(symLine);
    
    int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
    double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
    string metaLine = StringFormat("#META:%d,%f\n", digits, point);
    SendRawString(metaLine);
    
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

    // Ensure valid millisecond timestamp
    long ts_msc = tick.time_msc;
    if(ts_msc <= 0)
    {
        ts_msc = (long)tick.time * 1000 + (GetMicrosecondCount() % 1000000) / 1000;
    }

    // High precision volume
    double vol = tick.volume_real > 0 ? tick.volume_real : (double)tick.volume;
    if(vol <= 0) vol = 1.0;

    // Format: time_msc,bid,ask,last,volume,flags
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
