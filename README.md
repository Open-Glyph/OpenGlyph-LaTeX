# OpenGlyph-LaTeX · 古文字的代码输入与字体排印

已有隶定字用编号输入；字库没有的形，改部件、增饰笔、删笔、调比例，再编成字体。正文不再夹杂一张张缺字图片。

**v0.2.0**：附带从 GlyphWiki `ebag_s` 源码重新编译的 **22,583 个字形**、38,462 份字形及依赖程序，新增JSON模块复用和记录抽取，支持衔接图像检索后的造字项目。普通写作仍只需要 LaTeX；不需要账号、模型、Python、Node 或联网服务。

- [下载发行包](https://github.com/Open-Glyph/OpenGlyph-LaTeX/releases/latest)
- [中文使用指南](docs/使用指南.md)
- [排印版手册 PDF](doc/openglyph-doc.pdf)
- [可编译示例](main.tex) · [示例 PDF](main.pdf)
- 解压后双击 `字形索引.html`，按来源编号或部件查找并复制 LaTeX 命令。

## 先写起来

下载 `openglyph-overleaf-v0.2.0.zip`，上传到 Overleaf，新建项目，选择 **XeLaTeX**，编译 `main.tex`。也可以解压到本地，用 XeLaTeX 或 Tectonic 编译。

最小用法：把 `openglyph.sty` 和 `ebag/` 放在论文项目中。

```tex
\documentclass[UTF8]{ctexart}
\usepackage{openglyph}
\OpenGlyphLoad{ebag}

\begin{document}
这个字可以直接排进正文：\ebag{s030-067}。
另外两例：\ebag{s131-009}、\ebag{s162-428}。
\end{document}
```

`\ebag{s030-067}` 是对 `\OpenGlyph{ebag:s030-067}` 的简写。输入的都是 ASCII 编号，既不用先打出稀有字，也不用记 PUA。

字体是实心矢量 OpenType/CFF，PDF 内嵌字体，正文是文本，不用图片代字。PUA 是字体局部地址，不是正式 Unicode 身份；复制到其他软件要带上对应字体。

## 库里没有，自己造一个

首版附带离线编译器，只接受高层部件操作，不要求逐笔填写 KAGE 原始代码。需要 Python 3.10+、Node.js，以及 `requirements-build.txt` 中的两项 Python 依赖。

```sh
python3 -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-build.txt

# 查看编号层级
python scripts/openglyph.py inspect ebag:s030-067 --node r4 -o component-preview

# 四种修改的完整示例；输出目录必须是新目录
python scripts/openglyph.py build examples/newforms.json -o myglyphs
```

在论文导言区增加：

```tex
\OpenGlyphLoad{myglyphs}
```

正文便可以写：

```tex
换部件后的字为\gwglyph{my:n1}，
添一点为\gwglyph{my:n2}，
删一笔为\gwglyph{my:n3}，
调比例为\gwglyph{my:n4}。
```

`examples/newforms.json` 的输入格式：

```json
{
  "schema": "openglyph.project.v1",
  "namespace": "my",
  "glyphs": [
    {
      "id": "n2",
      "base": "ebag:s030-067",
      "edits": [
        {"op":"insert","parent":"root","id":"inner_dot",
         "glyph":"primitive:dot","box":[77,129,119,167]}
      ]
    }
  ]
}
```

同一论文的新版字库用 `--allocation 旧目录/allocation.json` 保持已有地址；删除过的槽位不挪给另一个字。新的字形内容与旧版仍通过哈希区分。

打开 `component-preview/index.html` 可以看到编号对应的真实部件图，不必对着编号猜。单独部件的避让细节与整字可能不同，编辑后仍应看完整字形。

## 分层设计

新版可用 `modules` 定义复合部件，用 `module:名称` 在其它部件或字形中引用；`select` 可按实际节点抽取已有笔画组。例见 [modules.json](examples/modules.json)，与远端图像工具的衔接见 [联动排印](docs/联动排印.md)。不是让模型逐笔编写KAGE；网络检索是可选的独立步骤，正常LaTeX编译仍离线。

```text
已有 ebag_s 编号 ──────────────→ 随包 OTF + 字形映射 ─→ openglyph.sty ─→ 论文 PDF
ASCII 部件编辑 → 本地 KAGE → 新 OTF + 固定版本程序 ────┘
```

造字发生在写作之前或修订时。正常 LaTeX 编译不执行外部命令，**不需要 `shell-escape`**，不把整套工具链搬进 Overleaf。

## 宏包接口

| 命令 | 用途 |
|---|---|
| `\OpenGlyphLoad{ebag}` | 加载已有隶定字；重复加载同一路径不会重复注册 |
| `\ebag{s030-067}` | 用来源编号排印 |
| `\gwglyph{my:n1}` / `\OpenGlyph{my:n1}` | 调用自造字 |
| `\OpenGlyphAlias{my-name}{ebag:s030-067}` | 创建自己的短别名 |
| `\OpenGlyphSequence{my:n1,my:n2}` | 按给定次序排印多个字 |
| `\OpenGlyphIfExistsTF{id}{存在分支}{不存在分支}` | 检查是否已注册 |

找不到 ID、重复编号或字体缺字会明确报错，不静默改成近似常用字。

## 重要边界

- 这是排印与局部造字工具，不是 OCR，不负责判断文献字的正确释读。
- `ebag_s` 来源编号、部件编号、字形内容哈希、字体局部 PUA 和学术释读分别保存，不能互相替代。
- 本套字体没有采用旧 SEAL 字体位于平面 10–13 的自定义地址；已有字使用标准私用区 PUA-A 内的局部地址，通过宏包映射调用。
- 编译成功不等于字形核定。研究者仍应对照来源，尤其是缺笔、饰笔、连接和孔洞。
- 比例改变只是新的排印字样，不自动成为不同文字。示例四个新形不虚构出处与读音。
- 不包含扫描页、私有论文、用户文件、原有 SEAL 字体或未经确认许可的本地构字注释表。
- 首版重点支持 XeLaTeX / Tectonic。LuaLaTeX 分支为实验兼容，尚不作为已验证平台；pdfLaTeX 不支持。整篇竖排和复杂校勘版式应配合相应排版宏包。
- 当前在 GitHub 发布，不宣称已收录 CTAN、TeX Live 或 MiKTeX。

## 来源与许可

我们自己的宏包、编译器与文档采用 [MIT](LICENSE)。现成字形来自 **GlyphWiki 的 ebag_s 及其依赖程序**，原数据许可证明确允许修改、复制与再分发，包括商业和非商业用途；原文见 [GlyphWiki.txt](licenses/GlyphWiki.txt)。KAGE 引擎源码按其 GPL v3 许可证随包保留。

感谢引得市及 GlyphWiki 贡献者的字形建设。这里保留来源编号，不将原字形据为 OpenGlyph 原创。详细来源、文件哈希和许可区分见 [第三方说明](THIRD-PARTY-NOTICES.md) 和 [data/provenance.json](data/provenance.json)。

## English summary

OpenGlyph is a LaTeX package for named, font-backed historical Chinese glyphs. It ships a newly compiled OTF containing 22,583 GlyphWiki `ebag_s` forms and an optional offline component-edit compiler. Use `\OpenGlyphLoad{ebag}` and `\ebag{s030-067}`; custom bundles use their own namespaces. No shell escape or network service is involved in ordinary typesetting. Font-local PUA addresses are not character identity, and generated forms require human scholarly review. First-release validation targets XeLaTeX/Tectonic; LuaLaTeX remains experimental. See the separate licenses for OpenGlyph code, GlyphWiki data, and the GPL KAGE engine.
