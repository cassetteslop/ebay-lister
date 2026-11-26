LOG = []
def _rec(kind):
    def f(title, msg, **k):
        LOG.append((kind, msg)); return ANSWER
    return f
ANSWER = True
showinfo = _rec("info"); showwarning = _rec("warning"); showerror = _rec("error"); askyesno = _rec("yesno")
askyesnocancel = _rec("yesnocancel")
