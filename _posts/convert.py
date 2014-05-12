import sys

if __name__ == "__main__":
    filename = sys.argv[1]
    s = None
    with open('test.md', 'r') as f:
        s = f.read()
        s = s.replace('[color=red][b]', '### ').replace('[/color][/b]', '')
        s = s.replace('[b][color=red]', '### ').replace('[/b][/color]', '')
        lastend = 0
        while lastend < len(s):
            begin = s.find('[code]', lastend)
            if begin == -1:
                begin = len(s)
            # s = s[:lastend] + s[lastend:begin].replace('_', '\\_').replace('<', '&lt;').replace('>', '&gt;') + s[begin:] # replace('=', '\\=')
            lastend = s.find('[/code]', begin)
            if lastend == -1:
                lastend = len(s)
            else:
                lastend += len('[code]')
            
        s = s.replace('[code]', '{% highlight cpp %}').replace('[/code]', '{% endhighlight %}')
        
    with open(filename, 'w') as f:
        f.write(s)
