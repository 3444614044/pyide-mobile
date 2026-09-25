"""编辑器控件：有 pygments 就用带高亮的 CodeInput，否则退回原生 TextInput。

单独成文件是为了让无头测试能只 import 它（不牵出 kivy.core.window）。
"""
from kivy.uix.textinput import TextInput

try:
    from kivy.uix.codeinput import CodeInput
    from pygments.lexers import PythonLexer

    class CodeArea(CodeInput):
        def __init__(self, **kw):
            kw.setdefault("lexer", PythonLexer())
            super().__init__(**kw)

except Exception:  # noqa: BLE001 - 没装 pygments 也要能跑
    class CodeArea(TextInput):
        pass
