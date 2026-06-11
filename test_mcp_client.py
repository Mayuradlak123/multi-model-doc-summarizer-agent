import subprocess
import json
import sys
import os
import time

def read_line_with_timeout(process, timeout=5):
    """Reads a line from stdout with a timeout."""
    start_time = time.time()
    while True:
        line = process.stdout.readline()
        if line:
            return line.strip()
        if time.time() - start_time > timeout:
            return None
        time.sleep(0.1)

def test_mcp_server():
    print("--------------------------------------------------")
    print("Verifying Model Context Protocol (MCP) Server stdio...")
    print("--------------------------------------------------")
    
    # Launch mcp_server.py in stdio mode as a subprocess
    process = subprocess.Popen(
        [sys.executable, "mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # Give process a moment to initialize
        time.sleep(1)
        if process.poll() is not None:
            print("[FAILED] MCP server process terminated immediately.")
            stderr_out = process.stderr.read()
            print(f"Stderr: {stderr_out}")
            return
            
        print("[SUCCESS] MCP Server subprocess started.")
        
        # 1. Send JSON-RPC 'initialize' request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"}
            }
        }
        
        print("\nSending 'initialize' request...")
        process.stdin.write(json.dumps(init_request) + "\n")
        process.stdin.flush()
        
        # Read initialize response
        resp_line = read_line_with_timeout(process)
        if not resp_line:
            print("[FAILED] No response received from server for 'initialize' request.")
            return
            
        try:
            resp_data = json.loads(resp_line)
            print(f"[SUCCESS] Received initialize response. Protocol Version: {resp_data.get('result', {}).get('protocolVersion')}")
        except Exception as e:
            print(f"[FAILED] Failed to parse initialize response: {resp_line}. Error: {str(e)}")
            return
            
        # Send 'initialized' notification (standard MCP protocol flow)
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        process.stdin.write(json.dumps(initialized_notification) + "\n")
        process.stdin.flush()
        
        # 2. Send 'tools/list' request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        print("\nSending 'tools/list' request...")
        process.stdin.write(json.dumps(tools_request) + "\n")
        process.stdin.flush()
        
        resp_line = read_line_with_timeout(process)
        if not resp_line:
            print("[FAILED] No response received for 'tools/list'.")
            return
            
        try:
            resp_data = json.loads(resp_line)
            tools_list = resp_data.get("result", {}).get("tools", [])
            print(f"[SUCCESS] Exposed Tools Found: {len(tools_list)}")
            for t in tools_list:
                print(f"  - Tool: {t['name']}")
                print(f"    Description: {t['description']}")
                
            tool_names = [t["name"] for t in tools_list]
            assert "list_documents" in tool_names, "list_documents tool missing"
            assert "summarize_local_file" in tool_names, "summarize_local_file tool missing"
            assert "chat_with_document" in tool_names, "chat_with_document tool missing"
            assert "get_pipeline_timeline" in tool_names, "get_pipeline_timeline tool missing"
        except Exception as e:
            print(f"[FAILED] Failed to parse tools/list response: {resp_line}. Error: {str(e)}")
            return
            
        # 3. Call the 'list_documents' tool
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "list_documents",
                "arguments": {}
            }
        }
        
        print("\nCalling 'list_documents' tool...")
        process.stdin.write(json.dumps(call_request) + "\n")
        process.stdin.flush()
        
        resp_line = read_line_with_timeout(process)
        if not resp_line:
            print("[FAILED] No response received for tools/call.")
            return
            
        try:
            resp_data = json.loads(resp_line)
            content_list = resp_data.get("result", {}).get("content", [])
            if content_list and len(content_list) > 0:
                # The response content text is usually JSON encoded in a text wrapper for MCP
                text_content = content_list[0].get("text", "")
                docs = json.loads(text_content)
                print(f"[SUCCESS] Tool returned {len(docs)} document records from PostgreSQL!")
            else:
                print("[SUCCESS] Tool executed successfully but returned empty result list.")
        except Exception as e:
            print(f"[FAILED] Failed to parse tools/call response: {resp_line}. Error: {str(e)}")
            return
            
    finally:
        # Clean shutdown of subprocess
        process.terminate()
        process.wait()
        print("\nMCP server process terminated cleanly.")
        
    print("\nAll MCP stdio JSON-RPC checks passed successfully!")

if __name__ == "__main__":
    test_mcp_server()
