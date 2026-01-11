from pythonosc.udp_client import SimpleUDPClient
import time

client = SimpleUDPClient("127.0.0.1", 1234)

print("Sender fadeTrig = 1")
client.send_message("/rnbo/inst/0/params/fadeTrig", 1)
time.sleep(3)

print("Sender fadeTrig = 0")
client.send_message("/rnbo/inst/0/params/fadeTrig", 0)

print("Done!")
