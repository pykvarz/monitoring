from services import PingService
import logging

logging.basicConfig(level=logging.DEBUG)

def test():
    print("Testing 127.0.0.1...")
    res = PingService.ping_host("127.0.0.1")
    print(f"127.0.0.1: {res}")
    
    print("Testing 8.8.8.8...")
    res = PingService.ping_host("8.8.8.8")
    print(f"8.8.8.8: {res}")
    
    print("Testing invalid host...")
    res = PingService.ping_host("invalid.host.local")
    print(f"invalid: {res}")

if __name__ == "__main__":
    test()
