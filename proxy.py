from socket import *
from urllib.parse import urlparse
import threading
import sys,datetime , argparse ,time


BUFSIZE = 2048
TIMEOUT = 1
CRLF = '\r\n'
connectionnum = 1
MT = False
PC = False
svrlist = {}
month = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May',
'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']




# Dissect HTTP header into line(first line), header(second line to end), body
def parseHTTP(data):
	
	header = {}
	len = data.find(b'\r\n\r\n')
	body = data[(len+4):]

	ind = data.split(b'\r\n')
	line = ind[0].decode()
	del ind[0]
	for l in ind :
		if l == b'':
			break
		tmp = l.split(b": ")
		header[tmp[0].decode()] = tmp[1].decode()
	


	return HTTPPacket(line, header, body)


# Receive HTTP packet with socket
# It support seperated packet receive
def recvData(conn):
    # Set time out for error or persistent connection end
    conn.settimeout(TIMEOUT)
    data = conn.recv(BUFSIZE)

    while b'\r\n\r\n' not in data:
        data += conn.recv(BUFSIZE)  
        if data == b'' : break  

    packet = parseHTTP(data)
    body = packet.body

        
    # Chunked-Encoding
    if packet.isChunked():
        readed = 0
        while True:
            while b'\r\n' not in body[readed:len(body)]:
                d = conn.recv(BUFSIZE)
                body += d
            size_str = body[readed:len(body)].split(b'\r\n')[0]
            size = int(size_str, 16)
            readed += len(size_str) + 2
            while len(body) - readed < size + 2:
                
                d = conn.recv(BUFSIZE)
                body += d
            readed += size + 2
            if size == 0: break
    
    # Content-Length
    elif packet.getHeader('Content-Length'):
        received = 0
        expected = packet.getHeader('Content-Length')
        #print(expected)
        if expected == None:
            expected = '0'
        expected = int(expected)
        received += len(body)
        #print(expected)       
        while received < expected:
            d = conn.recv(BUFSIZE)
            #print("")
            received += len(d)
            body += d
    packet.body = body
    return packet.pack()


# HTTP packet class
# Manage packet data and provide related functions
class HTTPPacket:
    # Constructer
    def __init__(self, line, header, body):
        self.line = line  # Packet first line(String)
        self.header = header  # Headers(Dict.{Field:Value})
        self.body = body  # Body(Bytes)
    
    # Make encoded packet data
    def pack(self):
        #print("get packed")
        ret = self.line + CRLF
        for field in self.header:
            ret += field + ': ' + self.header[field] + CRLF
        ret += CRLF
        ret = ret.encode()
        ret += self.body
        return ret
    
    # Get HTTP header value
    # If not exist, return empty string
    def getHeader(self, field):
        return self.header.get(field,"")
    
    # Set HTTP header value
    # If not exist, add new field
    # If value is empty string, remove field
    def setHeader(self, field, value):
    	getval = self.header.get(field,"")
    	if getval:
    		if value : self.header[field] = value   		
    		else : 
    			del self.header[field]
    	else: self.header[field] = value
    
    # Get URL from request packet line
    def getURL(self):
        return self.line.split()[1]
    
    def isChunked(self):
        return 'chunked' in self.getHeader('Transfer-Encoding')


# Proxy handler thread class
class ProxyThread(threading.Thread):
    def __init__(self, conn, addr,messageNum):
        #svrlist = []
        super().__init__()
        self.conn = conn  # Client socket
        self.addr = addr  # Client address
        self.messageNum = messageNum

    
    # Thread Routine
    def run(self):
        global svrlist, month
        client_ip, client_port = self.addr

        
        while True:
            try:
                str_time = datetime.datetime.now()
                t=str(str_time)
                now = t.split('-')
                nowyear = now[0]
                nowmonth = month[int(now[1])]
                nowday = now[2].split()[0]
                nowtime = str(t.split()[1])

                current_time = nowday+"/"+nowmonth+"/"+nowyear+" "+nowtime # set datatime 
                
                svr = None
                address= ('','')
                data = recvData(self.conn) #recieve data form client
                req = parseHTTP(data) #request message
                url = urlparse(req.getURL()) #parse url for take address from message     
                       
                ip = str(url.netloc)
                port = 80
                
                if req.line.split()[0] == "CONNECT": #if method of message is connect, just print it and detour it
                	print("[%d] %s" %(self.messageNum,str(current_time)))
                	print("[%d] > Connection from %s:%d" %(self.messageNum, client_ip,client_port))
                	print("[%d] > %s" %(self.messageNum,req.line))
                	self.conn.close()
                	break #detour connect
          
                # Do I have to do if it is not persistent connection?
    
                # Remove proxy infomation
                if req.getHeader('Proxy-Connection'): # if there is Proxy-Connection header, its 
                	req.setHeader('Proxy-Connection','')
                if PC : 
                	req.setHeader('Connection','keep-alive')
                else :
                	req.setHeader('Connection', 'close')
    
                # Server connect
                address = (ip,port)
                index = -1
                if PC : 
                	try:                		
                		server = svrlist.get(address,"")
                		#for socket reuse                    	
                		if server == "": # if fisrt use this port , connect
                			
               				try:
               					svr = socket(AF_INET, SOCK_STREAM)
                				svr.connect(address)
                				
                			
                				 #connect to server               
                			except:             				

                				self.conn.close()
                				#svr.close()
                				break

                			lut = datetime.datetime.now()       
                			svrlist[address]= [svr,lut]                		
                			
                		else : 
                			lut = datetime.datetime.now()               			               			
                			svr = server[0]
                			svrlist[address] = [svr,lut]
                		

                	except Exception as e:
                		break 
       
                
                	
                else :	#non pc mode
                	svr = socket(AF_INET, SOCK_STREAM)                
                	try:
                		svr.connect(address) #connect to server               
                	except:
                		self.conn.close()
                		#svr.close()
                		break		
                # and so on...
    
                # send a client's request to the server
                svr.sendall(req.pack())
    
                # receive data from the server              
                
                data = recvData(svr)              
                res = parseHTTP(data)
                             
                # Set content length header
                
                if res.isChunked() : 
                	res.setHeader('Content-Length',str(sys.getsizeof(res.body)-33))
                  
                # If support pc, how to do socket and keep-alive?


                if PC :
                	res.setHeader('Connection','keep-alive')
                else :               	 
                	res.setHeader('Connection', 'close')
                	
                	
                	
                
                self.conn.sendall(res.pack()) 

                if not PC : svr.close()
                content_type = res.getHeader('Content-Type')
                #content_type = ''
                print("[%d] %s" %(self.messageNum,str(current_time)))
                print("[%d] > Connection from %s:%d" %(self.messageNum, client_ip,client_port))
                print("[%d] > %s" %(self.messageNum,req.line))                
                print("[%d] < %s" %(self.messageNum,res.line))
                print("[%d] < %s %dbytes" %(self.messageNum, content_type,sys.getsizeof(res.body)-33)) #print bdoy size as content-length
                print("")

                self.conn.close()
                break

            except Exception as e:
            	print(e)
            	if svr is not None: svr.close() #close server
            	
            	
            	self.conn.close()
            	
            	break
            except KeyboardInterrupt:
            	svr.close()

            	
            	self.conn.close()
            	sys.exit()
            	break
            	




                
def main():
    global MT , PC
    messageNum = 1
    parser = argparse.ArgumentParser(description='PorxyServer Option')
    parser.add_argument('port', type = int ,default = 8888, help = "port number")
    parser.add_argument('-mt', action = "store_true", help="multithreading")
    parser.add_argument('-pc', action = "store_true", help="persistent connection")
    args = parser.parse_args()
    connlist = []
    threadlist = []
    try:
        port = int(args.port)
        sock = socket(AF_INET, SOCK_STREAM)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        host = "0.0.0.0"
        sock.bind((host, port))
        sock.listen(20)
        print('Proxy Server started on port %d at %s' % (port ,str(datetime.datetime.now())) )
        if args.mt : 
        	print("* Multithreading - [ON]")
        	MT = True
        else : 
        	print("* Multithreading - [OFF]")
        	MT = False 
        if args.pc : 
        	print("* Persistent Connection - [ON]")
        	PC = True
        else : 
        	print("* Persistent Connection - [OFF]")
        	PC = False

        while True:
            # Client connect
            conn, addr = sock.accept()

            # Start Handling

            pt = ProxyThread(conn, addr,messageNum)
            pt.start()

            messageNum += 1
            #print(svrlist)
            if not args.mt:
            	pt.join()

            current = datetime.datetime.now()
            if PC:
            	for key, value in svrlist.items() :           	
            		if int((current-value[1]).microseconds) > 100000000:
            			value[0].close()
            			del svrlist[key]

            #print(svrlist)
            		

    except Exception as e:
        print(e)
        pass
    except KeyboardInterrupt:    	
    	sock.close()
    	exit()



if __name__ == '__main__':
    main()

