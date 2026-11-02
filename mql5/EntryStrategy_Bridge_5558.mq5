//+------------------------------------------------------------------+
//|                                EntryStrategy_Bridge_5558.mq5    |
//|                    High-Speed Tick & Bar Bridge for Port 5558    |
//+------------------------------------------------------------------+
#property copyright "Entry Strategy Matrix"
#property link      ""
#property version   "1.01"
#property description "Streams MT5 real-time ticks to Entry Strategy App on Port 5558"

input string InpHost = "127.0.0.1";
input int    InpPort = 5558;

int client_socket = INVALID_HANDLE;
bool meta_sent = false;

int OnInit()
{
    Print("[EntryStrategy] Initializing Bridge on port ", InpPort, "...");
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

void ConnectSocket()
{
    if(client_socket != INVALID_HANDLE)
    {
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
    }
    
    client_socket = SocketCreate();
    if(client_socket == INVALID_HANDLE)
    {
        Print("[EntryStrategy] Failed to create socket. Error: ", GetLastError());
        return;
    }
    
    if(SocketConnect(client_socket, InpHost, InpPort, 1000))
    {
        Print("[EntryStrategy] Connected successfully to port ", InpPort);
        meta_sent = false;
        SendMeta();
    }
    else
    {
        // App might not be running yet, will retry on subsequent ticks
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
    }
}

void SendRawString(string data)
{
    if(client_socket == INVALID_HANDLE)
    {
        ConnectSocket();
        if(client_socket == INVALID_HANDLE) return;
    }

    uchar buffer[];
    StringToCharArray(data, buffer, 0, StringLen(data));
    int sent = SocketSend(client_socket, buffer, ArraySize(buffer));
    if(sent < 0)
    {
        Print("[EntryStrategy] Socket send failed. Reconnecting...");
        SocketClose(client_socket);
        client_socket = INVALID_HANDLE;
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
    
    meta_sent = true;
}

void OnTick()
{
    MqlTick tick;
    if(!SymbolInfoTick(_Symbol, tick)) return;

    if(!meta_sent || client_socket == INVALID_HANDLE)
    {
        ConnectSocket();
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
