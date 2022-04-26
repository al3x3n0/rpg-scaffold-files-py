def apply_ident(s, n):
    lines = s.split('\n')
    ident = ' ' * n
    return '\n'.join([ident + line for line in lines]) + '\n'
