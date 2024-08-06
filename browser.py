import ssl
import socket
import tkinter
import tkinter.font

# Constants
SOCKETS = {}
FONTS = {}
WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

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
            
        s = SOCKETS.get((self.host, self.port))
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
            SOCKETS[(self.host, self.port)] = s        
            return content
        
        content = response.read()
        s.close()
        
        return content
    
class Browser:
    def __init__(self) -> None:
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack()
        self.scroll = 0
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)
        self.window.bind("<MouseWheel>", self.on_mousewheel)
        
    def on_mousewheel(self, e: tkinter.Event):
        max_y = self.display_list[-1][1]
        delta = e.delta
        if delta > 0 and self.scroll - 2 * delta < 0:
            self.scroll = 0
        elif delta < 0 and self.scroll + 2 * delta > max_y - HEIGHT:
            self.scroll = max_y - HEIGHT
        else:
            self.scroll -= 2 * delta
        self.draw()
        
    def scrollup(self, e: tkinter.Event):
        if self.scroll - SCROLL_STEP < 0:
            self.scroll = 0
        else:
            self.scroll -= SCROLL_STEP
        self.draw()
        
    def load(self, url: URL) -> None:
        body = url.request()
        tokens = lex(body)
        self.display_list = Layout(tokens).display_list
        self.draw()     
    
    def scrolldown(self, e: tkinter.Event):
        self.scroll += SCROLL_STEP
        self.draw()
        
    def draw(self) -> None:
        self.canvas.delete("all")
        
        for x, y, w, f in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=w, font=f, anchor="nw")
            
class Text:
    def __init__(self, text: str) -> None:
        self.text = text
        
class Tag:
    def __init__(self, tag: str) -> None:
        self.tag = tag

class Layout:
    def __init__(self, tokens) -> None:
        self.display_list = []
        self.line = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        for tok in tokens:
            self.token(tok)
        self.flush()

    def flush(self) -> None:
        if not self.line: return
        metrics = [font.metrics() for _, _, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent
        
        self.cursor_x = HSTEP
        self.line = []
        
    def token(self, tok) -> list:
        if isinstance(tok, Text):
            for word in tok.text.split():
                self.word(word)
        elif tok.tag == 'i':
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == 'b':
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        
    def word(self, word: str) -> None:
        font = get_font(self.size, self.weight, self.style)
        w = font.measure(word)
        self.line.append((self.cursor_x, word, font))   
        self.cursor_x += w + font.measure(" ")
        if self.cursor_x + w > WIDTH - HSTEP:
            self.flush()

def lex(body: str) -> list:
    out = []
    buffer = ""
    in_tag = False
    for c in body:
        if c == '<':
            in_tag = True
            if buffer: out.append(Text(buffer))
            buffer = ""
        elif c == '>':
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += c
    if not in_tag and buffer:
        out.append(Text(buffer))
    return out

def show(body: str, view_source: bool) -> None:
    if not view_source:
        in_tag = False
        for c in body:
            if c == '<':
                in_tag = True
            elif c == '>':
                in_tag = False
            elif not in_tag:
                print(c, end='')
    else:
        print(body)        
        
def get_font(size: int, weight: str, style: str) -> tkinter.font.Font:
    key = (size, weight, style)
    if key not in FONTS:
        font = tkinter.font.Font(size=size, weight=weight,
            slant=style)
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    return FONTS[key][0]
    
if __name__ == "__main__":
    import sys
    arg = '' 
    if len(sys.argv) < 2:
        arg = "file:///Users/jacobsiegumfeldt/Desktop/Andet/Mine projekter/browser/example.html"
    else:
        arg = sys.argv[1]
    Browser().load(URL(arg))
    tkinter.mainloop()