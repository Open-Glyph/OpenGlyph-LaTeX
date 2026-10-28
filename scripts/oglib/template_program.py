"""Small, typed template-edit programs; source strokes remain compiler data.

Edits address occurrence paths (r0/r2), not shared component names. Copy-on-write
keeps other uses of the same component unchanged. Record IDs do not renumber
after deletion. Original KAGE stretch/transform fields survive unchanged.
"""
from __future__ import annotations

import copy
import math
import re

from .catalog import hash_json, refs

SCHEMA = 'guwenzi.template-program.v1'
COMPILER = 'template-program-v1'
PRIMITIVES = {
    'loop': '1:12:13:20:20:20:180$1:2:2:20:20:180:20$1:22:23:180:20:180:180$1:2:2:20:180:180:180',
    'dot': '2:7:8:55:35:100:75:140:140',
    'bar': '1:0:0:20:100:180:100',
    'slash': '1:0:0:160:30:40:170',
}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('布局值须为有限数值。')
    return value


def box(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('box 必须为 [left,top,right,bottom]，使用部件的 200 单位局部字格。')
    numbers = [number(v) for v in value]
    if any(v != int(v) for v in numbers):
        raise ValueError('当前 KAGE 后端使用整数字格；不静默截断小数坐标。')
    if numbers[0] >= numbers[2] or numbers[1] >= numbers[3]:
        raise ValueError('布局框宽高必须为正。')
    return [int(v) for v in numbers]


def same_canvas_alias(fields):
    return (len(fields) >= 8 and fields[:7] == ['99','0','0','0','0','200','200']
            and all(float(x or 0) == 0 for x in fields[8:]))


class Instance:
    def __init__(self, name, table):
        self.name, self.table = name, table
        self.records = [{'id': f'r{i}', 'fields': fragment.split(':'), 'child': None}
                        for i, fragment in enumerate(table[name].split('$'))]
        self.used_ids = {row['id'] for row in self.records}

    def record(self, identifier):
        for row in self.records:
            if row['id'] == identifier:
                return row
        raise ValueError('节点不存在或已删除：' + identifier)

    def child(self, row):
        if row['fields'][0] != '99':
            raise ValueError('该节点是直接笔画记录，没有可展开的子部件。')
        if row['child'] is None:
            row['child'] = Instance(row['fields'][7], self.table)
        return row['child']

    def target(self, path):
        if not isinstance(path, str) or not re.fullmatch(r'(?:r[0-9]+|a_[a-z0-9_-]+)(?:/(?:r[0-9]+|a_[a-z0-9_-]+))*', path):
            raise ValueError('node 使用工具返回的节点路径，如 r0 或 r0/r2。')
        node, ids = self, path.split('/')
        for identifier in ids[:-1]:
            node = node.child(node.record(identifier))
        return node, node.record(ids[-1])

    def container(self, path):
        if path == 'root':
            return self
        node, row = self.target(path)
        return node.child(row)

    def emit(self, table):
        fragments = []
        for row in self.records:
            fields = list(row['fields'])
            if row['child'] is not None:
                fields[7] = row['child'].emit(table)
            fragments.append(':'.join(fields))
        if not fragments:
            raise ValueError('修改后的部件为空；不能输出空白模板。')
        data = '$'.join(fragments)
        if data == self.table[self.name]:
            return self.name
        name = 'openglyph-template-' + hash_json(data)
        if name in table and table[name] != data:
            raise ValueError('模板程序名冲突。')
        table[name] = data
        return name


class TemplateProgram:
    def __init__(self, catalog, base):
        self.catalog = catalog
        self.base = catalog.resolve(base)
        self.table = dict(self.base['table'])
        self.selections = [{k: self.base[k] for k in ('name','ref','closure_sha256')}]
        name = self.base['name']
        self.aliases = []
        while True:
            fragments = self.table[name].split('$')
            if len(fragments) != 1 or not same_canvas_alias(fragments[0].split(':')):
                break
            self.aliases.append(name)
            name = fragments[0].split(':')[7]
        self.root = Instance(name, self.table)
        self.edits = []

    def select(self, query):
        if isinstance(query, str) and query.startswith('primitive:'):
            primitive = query[10:]
            if '@' in primitive:
                primitive, version = primitive.rsplit('@', 1)
                if version != '1':
                    raise ValueError('未知图形模板版本；不会静默替换。')
            if primitive not in PRIMITIVES:
                raise ValueError('未知图形模板：' + primitive)
            name = 'openglyph-primitive-' + primitive + '-v1'
            data = PRIMITIVES[primitive]
            if name in self.table and self.table[name] != data:
                raise ValueError('图形模板与来源程序同名冲突。')
            self.table[name] = data
            return name, 'primitive:' + primitive + '@1'
        selected = self.catalog.resolve(query)
        for name, data in selected['table'].items():
            if name in self.table and self.table[name] != data:
                raise ValueError('同名依赖存在版本冲突：' + name)
        self.table.update(selected['table'])
        self.selections.append({k: selected[k] for k in ('name','ref','closure_sha256')})
        return selected['name'], selected['ref']

    def apply(self, action):
        if not isinstance(action, dict):
            raise ValueError('每个修改必须为操作对象。')
        action = copy.deepcopy(action)
        op = action.get('op')
        allowed = {'replace': {'op','node','glyph'}, 'drop': {'op','node'},
                   'place': {'op','node','box'}, 'move': {'op','node','delta'},
                   'insert': {'op','parent','id','glyph','box'},
                   'group': {'op','parent','id','nodes'}}
        if not isinstance(op,str) or op not in allowed or set(action) != allowed[op]:
            raise ValueError('不支持的修改操作或字段：' + str(op))
        if op in ('insert','group'):
            container = self.root.container(action['parent'])
            label = action['id']
            if not isinstance(label, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', label):
                raise ValueError('新增节点 id 使用 ASCII 小写字母、数字、下划线或连字符。')
            identifier = 'a_' + label
            if identifier in container.used_ids:
                raise ValueError('新增节点 id 重复：' + label)
            if op == 'insert':
                bounds = box(action['box'])
                name, action['glyph'] = self.select(action['glyph'])
                container.records.append({'id': identifier,
                    'fields': ['99','0','0',*map(str,bounds),name], 'child': None})
            else:
                nodes=action['nodes']
                if not isinstance(nodes,list) or not nodes or any(not isinstance(n,str) for n in nodes) or len(set(nodes))!=len(nodes):
                    raise ValueError('group.nodes 须为当前层不重复的节点编号。')
                selected=[container.record(n) for n in nodes]
                indices=[container.records.index(r) for r in selected]
                if indices != list(range(indices[0],indices[0]+len(indices))):
                    raise ValueError('只允许按原顺序组合相邻记录，避免改变笔画覆盖顺序。')
                if any(r['fields'][0] in ('','0') for r in selected):
                    raise ValueError('不能将分隔符或作用域变换记录归并为普通部件。')
                emitted=dict(self.table)
                fragments=[]
                for row in selected:
                    fields=list(row['fields'])
                    if row['child'] is not None:fields[7]=row['child'].emit(emitted)
                    fragments.append(':'.join(fields))
                data='$'.join(fragments)
                name='openglyph-group-'+hash_json(data)
                emitted[name]=data
                self.table.update(emitted)
                child=Instance(name,self.table)
                child.records=selected
                child.used_ids={r['id'] for r in selected}
                container.records[indices[0]:indices[-1]+1]=[{'id':identifier,
                    'fields':['99','0','0','0','0','200','200',name], 'child':child}]
            container.used_ids.add(identifier)
        else:
            container, row = self.root.target(action['node'])
            if op == 'drop':
                if row['fields'][0] == '':
                    raise ValueError('来源分隔符不是可删除笔画。')
                if not any(r is not row and r['fields'][0] not in ('','0') for r in container.records):
                    raise ValueError('不能删除部件的全部记录。')
                container.records.remove(row)
            else:
                if row['fields'][0] != '99':
                    raise ValueError('此操作需要部件节点；直接笔画可 drop，或将它作为独立模块后编辑。')
                if op == 'replace':
                    name, action['glyph'] = self.select(action['glyph'])
                    row['fields'][7], row['child'] = name, None
                elif op == 'place':
                    row['fields'][3:7] = map(str, box(action['box']))
                elif op == 'move':
                    if not isinstance(action['delta'], list) or len(action['delta']) != 2:
                        raise ValueError('delta 须为 [dx,dy]。')
                    dx, dy = map(number, action['delta'])
                    bounds = [float(v) for v in row['fields'][3:7]]
                    row['fields'][3:7] = map(str, box([bounds[0]+dx,bounds[1]+dy,bounds[2]+dx,bounds[3]+dy]))
        self.edits.append(action)

    def describe(self, node='root'):
        container = self.root.container(node)
        rows = []
        for record in container.records:
            fields = record['fields']
            path = record['id'] if node == 'root' else node + '/' + record['id']
            if fields[0] == '99':
                primitive = next((p for p in PRIMITIVES if fields[7] == 'openglyph-primitive-' + p + '-v1'),None)
                local=fields[7].startswith('openglyph-group-')
                selected = self.catalog.resolve(fields[7]) if primitive is None and not local else None
                rows.append({'node': path, 'kind': 'component', 'glyph_name': fields[7],
                             'glyph_ref': selected['ref'] if selected else ('primitive:' + primitive + '@1' if primitive else None),
                             'local_module':local,
                             'locally_edited': record['child'] is not None and record['child'].emit(dict(self.table)) != fields[7],
                             'box': [float(v) for v in fields[3:7]],
                             'placement_flags_preserved': fields[1:3] + fields[8:],
                             'simple_placement': fields[1:3] == ['0','0'] and all(float(x or 0)==0 for x in fields[8:]),
                             'actions': ['replace','drop','place','move','inspect_children']})
            else:
                rows.append({'node': path, 'kind': 'source_record', 'record_type': fields[0],
                             'actions': ['drop'] if fields[0] else [], 'source_record_preserved': True})
        return {'schema': 'guwenzi.template-inspection.v1', 'base': self.base['ref'],
                'root_aliases': self.aliases, 'inspected_node': node, 'glyph_name': container.name,
                'nodes': rows, 'coordinate_space': 'parent_component_200_unit_grid',
                'next_step': 'Select by actual previews. Nested occurrences are independent; node IDs do not renumber after drop.',
                'program': {'schema': SCHEMA, 'base': self.base['ref'], 'edits': list(self.edits)}}

    def compile(self):
        table = dict(self.table)
        root = self.root.emit(table)
        if root == self.root.name:
            root = self.base['name']
        closure = {}
        pending = [root]
        while pending:
            name = pending.pop()
            if name in closure:
                continue
            if name not in table:
                raise ValueError('编译缺少部件：' + name)
            closure[name] = table[name]
            pending.extend(refs(table[name]))
        program = {'schema': SCHEMA, 'base': self.base['ref'], 'edits': copy.deepcopy(self.edits)}
        selected = list({r['ref']: r for r in self.selections}.values())
        recipe = {'schema': 'guwenzi.kage-construction.v1', 'root': root, 'table': closure,
                  'source_kind': 'printed', 'compiler': COMPILER, 'template_program': program,
                  'selected_components': selected, 'reconstruction_label': '模板原形复用' if not self.edits else '模板局部修改'}
        info = {'mode': 'template_reuse' if not self.edits else 'template_edit', 'compiler': COMPILER,
                'base_glyph_ref': self.base['ref'], 'program': program, 'program_sha256': hash_json(program),
                'recipe_sha256': hash_json(recipe), 'selected_components': selected,
                'source_equivalence_verified': False, 'unicode_identity_verified': False,
                'raw_strokes_authored_by_model': False, 'occurrence_edits_are_local': True,
                'unchanged_source_records_preserved': True}
        return recipe, info


def compile_program(catalog, value):
    if not isinstance(value, dict) or set(value) != {'schema','base','edits'} or value['schema'] != SCHEMA or not isinstance(value['edits'], list):
        raise ValueError('模板程序需要 schema/base/edits；不接受原始 KAGE 笔画串。')
    program = TemplateProgram(catalog, value['base'])
    for index, edit in enumerate(value['edits']):
        try:
            program.apply(edit)
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError(f'edits[{index}]: {exc}') from exc
    return program.compile()
