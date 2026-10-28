# OpenGlyph-LaTeX v0.1.0

古文字隶定字现在可以像 LaTeX 公式一样，用 ASCII 编号写进论文。

- 开箱带有 22,583 个 GlyphWiki ebag_s 字形，保留来源编号；OTF 为重新编译的真实轮廓字体，不是图片字。
- 已有字：`\OpenGlyphLoad{ebag}` 后使用 `\ebag{s030-067}`。
- 自造字：离线按部件编号替换、添饰笔、删笔、调比例；生成新字体后用 `\gwglyph{my:n1}` 混排。
- 附离线字形索引、可编译论文示例、中文手册、四种局部编辑示例和固定版本源码。
- 常规 LaTeX 编译不联网、不调用模型、不需要 shell-escape。

## 下载哪个

- **只写论文 / 使用 Overleaf**：`openglyph-overleaf-v0.1.0.zip`，上传为项目后选 XeLaTeX，编译 `main.tex`。
- **还要造新字 / 开发**：`openglyph-v0.1.0.zip`，包含离线编译器、许可、测试和完整的对应程序子集。
- **先看效果**：`openglyph-example.pdf`；教程见 `openglyph-manual.pdf`。
- `SHA256SUMS.txt` 用于校验发行文件。

## 验证与边界

首版做了 13 项 Python 测试（含生成式属性检查）、9 项独立目录 LaTeX 正反例测试，以及 22,583 个内置字的码位、轮廓和映射完整性检查。示例 PDF 已确认使用嵌入字体、没有图片代字。

这不是 22,583 字的学术核定：字形选取、释读和与文献原形的对应仍由研究者确认。PUA 是字体局部地址，不是标准 Unicode 身份。比例变化不自动构成另一个文字。

目前验证了 XeLaTeX 核心的 Tectonic；LuaLaTeX 属实验兼容，pdfLaTeX 不支持。GitHub 发布不等于 CTAN/TeX Live/MiKTeX 已收录。

## 来源与许可

OpenGlyph 自有代码为 MIT；GlyphWiki 数据及衍生字形按其明确允许修改与再分发的许可保留；KAGE 引擎源码按 GPL v3 保留。完整说明见 THIRD-PARTY-NOTICES.md。不包含本机 SEAL 字体、私人论文、用户文档或未确认许可的本地注释表。
