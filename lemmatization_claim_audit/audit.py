"""Deterministic documentation and Python AST inspection."""
import ast
import re
from pathlib import Path
from .phrases import LEMMA, NOLEMMA, GENERIC_NAMES

EXCLUDED = {'.git', '__pycache__', '.venv', 'venv', 'env', '.env', 'virtualenv'}


def evidence(source, blocked=()):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    nodes = list(ast.walk(tree))
    shadow = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    imports = {}
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                imports[a.asname or a.name] = (n.module or '') + '.' + a.name
    def resolve(n):
        if isinstance(n, ast.Name):
            return '' if n.id in shadow else imports.get(n.id, '')
        if isinstance(n, ast.Attribute):
            base = resolve(n.value)
            return base + '.' + n.attr if base else ''
        return ''
    def kind(n):
        if not isinstance(n, ast.Call):
            return ''
        name = resolve(n.func)
        if name.startswith('nltk.') and name.endswith('.WordNetLemmatizer') and 'WordNetLemmatizer' not in shadow:
            return 'nltk'
        if name.startswith('spacy_lemmatizer.') and name.endswith('.Lemmatizer') and 'Lemmatizer' not in shadow:
            return 'spacy'
        return ''
    blocked_values = set(blocked)
    for n in nodes:
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call):
            func = n.value.func
            func_name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
            if func_name in shadow:
                blocked_values.update(t.id for t in n.targets if isinstance(t, ast.Name))
    values = {}
    # Propagate simple instance aliases without crossing module boundaries.
    for _ in range(len(nodes)):
        changed = False
        for n in nodes:
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                value = n.value
                k = kind(value) or (values.get(value.id, '') if isinstance(value, ast.Name) else '')
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Name) and k and values.get(t.id) != k:
                        values[t.id] = k
                        changed = True
        if not changed:
            break
    def instance(n):
        return kind(n) or (values.get(n.id, '') if isinstance(n, ast.Name) else '')
    for n in nodes:
        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and n.attr in {'lemma', 'lemma_'}:
            return True
        if not isinstance(n, ast.Call):
            continue
        name = resolve(n.func)
        if name in {'lemminflect.getLemma', 'simplemma.text_lemmatizer'} and name.rsplit('.', 1)[1] not in shadow:
            return True
        if instance(n.func) == 'spacy':
            return True
        if isinstance(n.func, ast.Attribute):
            attr = n.func.attr
            if attr in shadow:
                continue
            if isinstance(n.func.value, ast.Name) and n.func.value.id in blocked_values:
                continue
            k = instance(n.func.value)
            if k == 'nltk' and attr == 'lemmatize':
                return True
            # Imported constructors need their actual instance, not a class call.
            base = resolve(n.func.value)
            if attr in GENERIC_NAMES and not base.endswith(('.WordNetLemmatizer', '.Lemmatizer', '.Pipeline')):
                return True
        elif isinstance(n.func, ast.Name) and name and name.rsplit('.', 1)[-1] in GENERIC_NAMES:
            return True
    return False


def prose(text):
    lines = []
    fenced = False
    for line in text.splitlines():
        if re.match(r'^\s*```', line):
            fenced = not fenced
        elif not fenced:
            lines.append(line.replace('`', ''))
    return '\n'.join(lines).lower()


def matches(text, phrases):
    found = []
    for phrase in sorted(phrases, key=len, reverse=True):
        start = text.find(phrase)
        while start >= 0:
            found.append(phrase)
            text = text[:start] + ' ' * len(phrase) + text[start + len(phrase):]
            start = text.find(phrase)
    return found, text


def audit(repo='.', ignore=(), decisions=None):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    files = []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        skip = any(part in EXCLUDED for part in path.relative_to(root).parts) or any(rel.startswith(p) for p in ignore)
        if not skip and path.is_file():
            # Detect virtual environments with custom directory names too.
            skip = any((parent / 'pyvenv.cfg').exists() for parent in path.parents if parent != root and root in parent.parents)
        if decisions is not None:
            decisions.append(('SKIP ' if skip else 'SCAN ') + rel)
        if not skip and path.is_file():
            files.append((path, rel))
    sources = {rel: path.read_text(encoding='utf-8') for path, rel in files if path.suffix == '.py'}
    exported = {}
    for rel, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        constructors = {'WordNetLemmatizer', 'Lemmatizer', 'Pipeline'}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in constructors:
                        constructors.add(alias.asname or alias.name)
        exported[rel] = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                         and isinstance(node.value, ast.Call)
                         and ((isinstance(node.value.func, ast.Name) and node.value.func.id in constructors)
                              or (isinstance(node.value.func, ast.Attribute) and node.value.func.attr in constructors))
                         for t in node.targets if isinstance(t, ast.Name)}
    backed = False
    for rel, source in sources.items():
        blocked = set()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target = (node.module or '').replace('.', '/') + '.py'
                if node.level:
                    target = str(Path(rel).parent / target)
                for alias in node.names:
                    if alias.name in exported.get(target, set()):
                        blocked.add(alias.asname or alias.name)
        if evidence(source, blocked):
            backed = True
            break
    findings = []
    for path, rel in files:
        shipped = rel == 'README.md' or (rel.startswith('docs/') and path.suffix == '.md')
        test = 'tests' in Path(rel).parts and path.suffix == '.md'
        if not shipped and not test:
            continue
        denial, remaining = matches(prose(path.read_text(encoding='utf-8')), NOLEMMA)
        claims, _ = matches(remaining, LEMMA)
        for phrase in (denial if backed and shipped else claims if not backed else []):
            negative = backed
            findings.append(dict(id='documented-no-lemmatization-claim-false' if negative else 'documented-lemmatization-claim-false', severity='HIGH' if shipped else 'MEDIUM', path=rel, phrase=phrase, verdict='FAIL', message='Documentation contradicts source evidence: ' + phrase))
    return findings
