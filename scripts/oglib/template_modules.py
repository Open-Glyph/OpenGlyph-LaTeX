"""JSON-only reusable modules and source-record selection, without raw strokes."""
import copy
import re

from .catalog import hash_json, refs
from .template_program import TemplateProgram, SCHEMA, PRIMITIVES


class ModuleCatalog:
    def __init__(self, source, definitions):
        if not isinstance(definitions, dict) or any(not re.fullmatch(r'[a-z][a-z0-9_-]*', k) for k in definitions):
            raise ValueError('modules 须为 ASCII 名称到部件程序的对象。')
        self.source, self.definitions = source, definitions
        self.table, self.resolved, self.active = {}, {}, set()

    def get(self, name):
        return self.table.get(name) or self.source.get(name)

    def resolve(self, query):
        if not isinstance(query, str):
            raise ValueError('部件引用须为字符串。')
        if query.startswith('module:'):
            key = query[7:]
            if key not in self.definitions:
                raise ValueError('缺少模块定义：' + key)
            if key in self.active:
                raise ValueError('模块循环引用：' + key)
            if key not in self.resolved:
                self.active.add(key)
                try:
                    value = self.definitions[key]
                    if not isinstance(value, dict) or 'modules' in value:
                        raise ValueError('模块定义使用同级 modules，不嵌套 modules。')
                    recipe, _ = compile_modular(self, value)
                    self.table.update(recipe['table'])
                    self.resolved[key] = dict(name=recipe['root'], ref=query,
                        closure_sha256=hash_json(recipe['table']), table=recipe['table'])
                finally:
                    self.active.remove(key)
            return self.resolved[key]
        if query.startswith('primitive:'):
            key = query[10:].removesuffix('@1')
            if key not in PRIMITIVES:
                raise ValueError('未知图形模板：' + key)
            name = 'openglyph-primitive-' + key + '-v1'
            table = {name: PRIMITIVES[key]}
            self.table.update(table)
            return dict(name=name, ref='primitive:' + key + '@1', closure_sha256=hash_json(table), table=table)
        expected = None
        name = query
        if query.startswith('gwk:'):
            pieces = query.split(':', 2)
            if len(pieces) == 3:
                _, expected, name = pieces
        if name not in self.table:
            return self.source.resolve(query)
        closure, pending = {}, [name]
        while pending:
            n = pending.pop()
            if n in closure:
                continue
            data = self.get(n)
            if not data:
                raise ValueError('模块依赖缺失：' + n)
            closure[n] = data
            pending.extend(refs(data))
        digest = hash_json(closure)
        if expected and expected != digest:
            raise ValueError('模块版本不匹配。')
        return dict(name=name, ref=f'gwk:{digest}:{name}', closure_sha256=digest, table=closure)


def instance(catalog, value):
    if (not isinstance(value, dict) or set(value) - {'schema', 'base', 'edits', 'select', 'modules'}
        or value.get('schema') != SCHEMA or not isinstance(value.get('edits'), list) or 'base' not in value):
        raise ValueError('模板程序需要 schema/base/edits，可选 modules/select；禁止原始笔画串。')
    wrapped = ModuleCatalog(catalog, value.get('modules', {})) if not isinstance(catalog, ModuleCatalog) or 'modules' in value else catalog
    # Validate all definitions, including unused cycles, before rendering.
    if 'modules' in value:
        for key in sorted(wrapped.definitions):
            wrapped.resolve('module:' + key)
    program = TemplateProgram(wrapped, value['base'])
    selection = value.get('select')
    if selection is not None:
        if not isinstance(selection, dict) or set(selection) != {'parent', 'nodes'}:
            raise ValueError('select 需要 parent 和 nodes，编号来自 inspect。')
        parent = program.root.container(selection['parent'])
        names = selection['nodes']
        if not isinstance(names, list) or not names or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
            raise ValueError('select.nodes 须为不重复的已有节点。')
        records = [parent.record(n) for n in names]
        indices = [parent.records.index(r) for r in records]
        if indices != sorted(indices) or any(r['fields'][0] in ('', '0') for r in parent.records):
            raise ValueError('不能重排或截取带作用域变换的记录。')
        program.root = copy.deepcopy(parent)
        program.root.records = copy.deepcopy(records)
        program.selected_root = True
    for i, edit in enumerate(value['edits']):
        try:
            program.apply(edit)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f'edits[{i}]: {exc}') from exc
    return program


def compile_modular(catalog, value):
    program = instance(catalog, value)
    recipe, info = program.compile()
    canonical = copy.deepcopy(info['program'])
    # Module references must remain replayable, not leak ephemeral compiler names.
    if str(value['base']).startswith('module:'):
        canonical['base'] = value['base']
    for original, normalized in zip(value['edits'], canonical['edits']):
        if str(original.get('glyph', '')).startswith('module:'):
            normalized['glyph'] = original['glyph']
    for key in ('select', 'modules'):
        if key in value:
            canonical[key] = copy.deepcopy(value[key])
    recipe['template_program'] = canonical
    info.update(program=canonical, program_sha256=hash_json(canonical))
    info['recipe_sha256'] = hash_json(recipe)
    return recipe, info
