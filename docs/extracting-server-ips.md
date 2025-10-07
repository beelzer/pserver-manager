# Guide: Extracting Server IPs from Game Applications

This guide documents the process of finding server IP addresses and ports for private server games by analyzing active network connections.

## Prerequisites

- Windows Command Prompt or PowerShell
- Game client running and connected to server
- Basic command line knowledge

## Method 1: Find by Process ID (Most Accurate)

This method identifies the exact IP by first finding the game process, then filtering connections by that process.

### Step 1: Find the Game Process

```bash
tasklist | findstr -i "java"
```

**Output Example:**
```
java.exe                     47656 Console                    1    760,940 K
```

The number in the second column is the Process ID (PID). In this example: `47656`

### Step 2: Find Connections for That Process

```bash
netstat -ano | findstr <PID> | findstr ESTABLISHED
```

**Example:**
```bash
netstat -ano | findstr 47656 | findstr ESTABLISHED
```

**Output Example:**
```
TCP    192.168.0.36:60729     195.66.212.32:580      ESTABLISHED     47656
```

The server IP and port is: `195.66.212.32:580`

## Method 2: Find by Known Port

If you know the game uses a specific port (e.g., RuneScape servers often use port 43594), you can search directly.

```bash
netstat -an | findstr ESTABLISHED | findstr :43594
```

**Output Example:**
```
TCP    192.168.0.36:50607     172.234.117.22:43594   ESTABLISHED
```

The server IP and port is: `172.234.117.22:43594`

## Method 3: Eliminate Common Traffic

Filter out common ports (HTTPS/HTTP) to reduce noise:

```bash
netstat -an | findstr ESTABLISHED | findstr -v "127.0.0.1 ::1 443 80"
```

This shows all established connections except:
- `127.0.0.1` - localhost IPv4
- `::1` - localhost IPv6
- `:443` - HTTPS traffic
- `:80` - HTTP traffic

**Use Case:** When you're not sure which port the game uses, but want to see non-web connections.

## Command Reference

### netstat

```bash
netstat -an      # Show all connections with numeric addresses
netstat -ano     # Include Process ID (PID) in output
```

**Flags:**
- `-a` - Display all connections and listening ports
- `-n` - Display addresses and port numbers in numerical form
- `-o` - Display owning process ID

### findstr

```bash
findstr "pattern"        # Search for pattern
findstr -i "pattern"     # Case-insensitive search
findstr -v "pattern"     # Invert match (show non-matching lines)
```

### tasklist

```bash
tasklist                    # List all running processes
tasklist | findstr "name"   # Filter by process name
```

## Complete Workflow Example

### Example: Finding Vidyascape World IPs

1. **Connect to World 1 in game**

2. **Find the connection:**
   ```bash
   netstat -an | findstr ESTABLISHED | findstr :43594
   ```

   **Result:** `50.116.63.13:43594` (US East)

3. **Switch to World 2 in game**

4. **Find the new connection:**
   ```bash
   netstat -an | findstr ESTABLISHED | findstr :43594
   ```

   **Result:** `172.234.117.22:43594` (Sweden)

5. **Switch to World 3 in game**

6. **Find the new connection:**
   ```bash
   netstat -an | findstr ESTABLISHED | findstr :43594
   ```

   **Result:** `172.105.188.37:43594` (Australia)

### Example: Finding Impact Server IP

1. **Launch Impact client**

2. **Find the Java process:**
   ```bash
   tasklist | findstr -i "java"
   ```

   **Result:** PID `47656`

3. **Find connections for that process:**
   ```bash
   netstat -ano | findstr 47656 | findstr ESTABLISHED
   ```

   **Result:** `195.66.212.32:580`

## Tips

1. **Close other applications** - Fewer running programs = easier to identify game connections

2. **Know common ports:**
   - OSRS/RuneScape: Often 43594
   - Many games: Custom high ports (8000-65000)
   - Official servers: Sometimes use standard ports (7777, 25565, etc.)

3. **Watch for multiple connections** - Some games maintain multiple connections (game server, chat server, etc.)

4. **Verify with ping** - Test the IP after extracting:
   ```bash
   ping 195.66.212.32
   ```

5. **Use TCPView (Optional)** - For a GUI alternative, download Microsoft's TCPView tool

## Troubleshooting

**Problem:** Too many results when using netstat

**Solution:** Add more filters or use Method 1 (Process ID) for precision

---

**Problem:** Connection shows as `TIME_WAIT` instead of `ESTABLISHED`

**Solution:** The connection was closed. Reconnect to the game and try again

---

**Problem:** Can't find Java process

**Solution:** The game might use a different executable. Try:
```bash
tasklist
```
Then look for the game's exe name manually

## Advanced: Monitoring Connection Changes

To watch connections in real-time:

```bash
# Windows - repeat every 2 seconds
while ($true) { cls; netstat -an | findstr ESTABLISHED | findstr :43594; sleep 2 }
```

This is useful when switching between game servers/worlds to see the IP change.

## Security Note

These techniques are for analyzing your own network connections to legitimate game servers you're already connected to. Always respect:
- Game server terms of service
- Privacy laws and regulations
- Network security policies
