"""画面员用的 API 速查（57号补丁六）：python api_ref.py
从 motion.py / components.py / fx.py / fxplus.py 源码直接列出公开函数、类方法的签名和文档首段，以及颜色等常量。
每次现跑、不手写，脚本改了速查自动跟着变。读它代替通读三份源码；要看某个函数的实现，再按行号去读那几行。"""
import ast, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ['motion.py', 'components.py', 'fx.py', 'fxplus.py']


def doc1(node, n=2):
    d = ast.get_docstring(node) or ''
    lines = [x.strip() for x in d.strip().splitlines() if x.strip()]
    return ' '.join(lines[:n])


def sig(node, src):
    return f'{node.name}({ast.unparse(node.args)})'


def main():
    out = [__doc__.splitlines()[0], '']
    for fn in FILES:
        p = os.path.join(HERE, fn)
        src = open(p, encoding='utf-8').read()
        tree = ast.parse(src)
        out.append(f'## {fn}')
        consts = []
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name.isupper() and not name.startswith('_'):
                    val = ast.get_source_segment(src, node.value) or ''
                    consts.append(f'{name}={val[:40]}' if len(val) <= 40 else name)
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_') and not node.name.startswith('cmd_'):
                d = doc1(node)
                out.append(f'- L{node.lineno} `{sig(node, src)}`' + (f' —— {d}' if d else ''))
            elif isinstance(node, ast.ClassDef) and not node.name.startswith('_'):
                d = doc1(node)
                out.append(f'- L{node.lineno} class `{node.name}`' + (f' —— {d}' if d else ''))
                for m in node.body:
                    if isinstance(m, ast.FunctionDef) and (not m.name.startswith('_') or m.name == '__init__'):
                        dm = doc1(m, 1)
                        out.append(f'    - `{sig(m, src)}`' + (f' —— {dm}' if dm else ''))
        if consts:
            out.append('- 常量：' + '，'.join(consts))
        out.append('')
    sys.stdout.reconfigure(encoding='utf-8')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
