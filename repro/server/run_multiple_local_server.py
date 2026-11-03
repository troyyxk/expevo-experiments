from esserver import ESServer
from config import local_host_ports, model_parameter
import threading
from model.model_loader import load_model
import sys


# Lists to keep track of servers and threads
servers = []
threads = []

def start_servers(model):
    """Start servers on ports 4001-4003 in non-blocking threads"""
    for port in local_host_ports["ports"]:
        # Create server instance
        server = ESServer("127.0.0.1", port, model)
        servers.append(server)
        
        # Create and start thread
        thread = threading.Thread(target=server.run)
        threads.append(thread)
        thread.start()
        
        print(f"Server started on port {port}")

def stop_servers():
    """Gracefully shutdown all servers and clean up threads"""
    for server in servers:
        server.close() 
    for thread in threads:
        thread.stop()
    print("\nAll servers stopped")

if __name__ == "__main__":
    model = None
    if len(sys.argv) == 2 and sys.argv[1] == "condence":
        print("Use Condence mode")
        model = load_model("local", model_parameter["path"])
    start_servers(model)
    try:
        # Keep main thread alive until user input
        input("Press Enter to stop servers...\n")
    except KeyboardInterrupt:
        print("\nShutdown signal received")
    finally:
        stop_servers()
