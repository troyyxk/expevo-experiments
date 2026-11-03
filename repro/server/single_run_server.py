from esserver import ESServer
from config import single_host_parameter

server = ESServer(single_host_parameter["host"], single_host_parameter["port"])
server.run()
