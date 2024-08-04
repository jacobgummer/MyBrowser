import ssl
import socket

sockets = {}

class URL:
    def __init__(self, url) -> None:
        self.view_source = False
        check = url.split(':', 1) 
        if check[0] == "view-source":
            self.view_source = True
            url = check[1]
            
        self.scheme, url = url.split("://", 1)
        assert self.scheme in ["http", "https", "file"]
        
        if '/' not in url:
            url = url + '/'
        self.host, url = url.split('/', 1)
        self.path = '/' + url

        if self.scheme == "http":
            self.port = 80
        elif self.scheme == "https":
            self.port = 443
        
        if ':' in self.host:
            self.host, port = self.host.split(':', 1)
            self.port = int(port)
            
    def request(self) -> str:
        if self.scheme == "file":
            content = ''
            try:
                f = open(self.path, 'r')
            except FileNotFoundError:
                print(f'Error: could not find file \'{self.path}\'')
            else:
                with f:
                    content = f.read()
            return content
            
        s = sockets.get((self.host, self.port))
        if not s:
            s = socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP
            )
            s.connect((self.host, self.port))
        
        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)
        
        request = f"GET {self.path} HTTP/1.0\r\n"
        request += f"Host: {self.host}\r\n"
        request += f"User-Agent: MyBrowser 0.1\r\n"
        request += "\r\n"
        s.send(request.encode("utf8"))
        
        response = s.makefile('r', encoding="utf8", newline="\r\n")
        statusline = response.readline()
        version, status, explanation = statusline.split(' ', 2)
        
        response_headers = {}
        while True:
            line = response.readline()
            if line == "\r\n": break
            header, value = line.split(':', 1)
            response_headers[header.casefold()] = value.strip()
        
        assert "transfer-encoding" not in response_headers
        assert "content-encoding" not in response_headers

        content_length = response_headers.get("Content-Length")
        if content_length:
            content = response.read(int(content_length))
            sockets[(self.host, self.port)] = s        
            return content
        
        content = response.read()
        s.close()
        
        return content


def show(body: str, view_source: bool) -> None:
    if not view_source:
        in_tag = False
        for c in body:
            if c == '<':
                in_tag = True
            elif c == '>':
                in_tag = False
            elif not in_tag:
                if c == "&lt":
                    c = '<'
                elif c == "&gt":
                    c = '>'
                print(c, end='')
    else:
        print(body)        
    
def load(url: URL) -> None:
    body = url.request()
    show(body, url.view_source)
    
if __name__ == "__main__":
    import sys
    arg = '' 
    if len(sys.argv) < 2:
        arg = "file:///Users/jacobsiegumfeldt/Desktop/Andet/Mine projekter/browser/example.txt"
    else:
        arg = sys.argv[1]
    load(URL(arg))