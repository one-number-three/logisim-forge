# logisim-forge

> 用代码画 Logisim 电路，并让 Logisim 自己验证它对不对。

![74LS138 3-8 译码器](assets/preview.png)

Logisim 没有插件 API、没有 socket、没有命令行控制接口。它唯一稳定的对外接口是
**`.circ` 文件**——一个纯文本 XML。这个项目就把这条缝隙做成工具：

- **写**：用 Python 描述电路（门、引脚、总线），生成 Logisim 能直接打开的 `.circ`；
- **验**：调用 **Logisim 自己的加载器和仿真器**，检查连线并按输入向量验证实际输出；
- **用**：包成 MCP server，任何支持 MCP 的客户端都能"说一句话画一个电路"。

## 为什么不是"直接点鼠标"

手工拖 8 个与非门 + 24 根地址线，改一次布局就要重拖一遍。代码生成的好处是**可复现、可 diff、可批量**：
74LS138 这种"一行公式展开成 27 个元件"的电路，用循环写只要 40 行，而且改地址位顺序只改一个数组。

难的是**坐标**：Logisim 按 10px 网格布局，门元件的 `loc` 是**输出端口**而不是左上角，
输入端口在左侧、偏移量随输入个数变化，加反相圈还会把端口再往左挪 10px。差一格线就连不上，
而 Logisim **不会报错**——它只是静静地画一根没接上的线。项目里把这些几何规则做成了表
（`logisim_forge/geometry.py`），并且用"读回校验"兜底。

## 安装

```bash
git clone https://github.com/one-number-three/logisim-forge
cd logisim-forge
pip install -e .            # 只需要 Python 3.9+
pip install -e ".[mcp]"     # 想跑 MCP server 再装这个
```

校验和仿真需要 **JDK 11+**（包括 `javac`）以及 Logisim jar/exe。本次新增的仿真桥已在 Windows 的 **Logisim-ITA 2.16.1.4** 上验证；其他版本需要自行确认 API 兼容性：

```bash
set LOGISIM_JAR=E:\Logisim\Logisim-ITA.exe          # Windows
export LOGISIM_JAR=/usr/share/logisim/logisim.jar   # Linux
export JAVA_HOME=/path/to/jdk                        # 或者确保 java 在 PATH 里
```

## 快速开始

```bash
python examples/74ls138.py     # 生成 examples/74ls138.circ 并自检
python -m logisim_forge verify examples/74ls138.circ
```

```json
{
  "components": 27,
  "wires": 96,
  "nets": 19,
  "dangling": [],
  "conflicts": {},
  "ok": true
}
```

`dangling` 是物理线段上的悬空端点；`conflicts` 检查指定驱动端所在的物理网络。库函数 `verify(..., drivers=...)` 才有调用者提供的驱动端；CLI 的 `verify` 没有提供驱动列表，不能据此断言没有短路。它只支持单子电路；多子电路使用下面的 `inspect`。静态检查不解析 Tunnel 同名连接及分线器的每一位，不能替代仿真。

### 用 Logisim 内核验证输入与输出

```bash
python -m logisim_forge inspect examples/74ls138.circ
python -m logisim_forge simulate examples/74ls138.circ main examples/74ls138-vectors.csv --image decoder.png
```

`simulate` 使用 Logisim 的 Loader 加载电路，设置输入 Pin，运行 Propagator，再读取输出 Pin 并对照 CSV 的期望值。每一行**保留上一行的状态**，因此可以在时序测试中先稳定数据和控制，再用 `CLK=0`、`CLK=1` 两行产生上升沿。CSV 必须列出选定电路中所有输入和输出 Pin 的唯一标签，支持额外的 `@x:y` 列检查电路坐标处的实际值。所有数字使用十进制；32 位数接受有符号整数或 0～4294967295，输出记录使用 Java 的有符号整数表示。空测试、错误预期、未定义值、位宽冲突和振荡会失败。

```csv
CLK,D,Q
0,0,0
0,1,0
1,1,1
1,0,1
0,0,1
1,0,0
```

以上是正边沿 D 触发器的示意向量：前两行先设置数据，第三行产生上升沿；保持时钟为 1 改变 D 不应再次触发。输入在同一行同时变化时没有建立时间保证。`--image` 使用 Logisim 原生绘图器渲染最后一行状态，不是 GUI 屏幕截图。仿真测试的范围取决于提供的向量；不会自动生成真值表，也不验证物理电路时序。

### 作为库用

```python
from logisim_forge import Circuit, verify

c = Circuit("main")
c.pin((110, 100), "A")            # 输入引脚（驱动电路）
c.not_gate((240, 100))            # 输出端口在 (240,100)，输入在 (210,100)
c.pin((320, 100), "Y", direction="out")

c.wire((110, 100), (210, 100))    # A -> 非门输入
c.wire((240, 100), (320, 100))    # 非门输出 -> Y
c.save("not.circ")

print(verify("not.circ", drivers=c.drivers()).as_dict())
```

### 作为 MCP server 用

```json
{
  "mcpServers": {
    "logisim": {
      "command": "python",
      "args": ["-m", "logisim_forge", "serve"],
      "env": { "LOGISIM_JAR": "E:/Logisim/Logisim-ITA.exe" }
    }
  }
}
```

| 工具 | 作用 |
| --- | --- |
| `create_circuit(name)` | 新建空电路 |
| `add_pin(x, y, label, direction)` | 加引脚，返回端口坐标 |
| `add_gate(kind, x, y, inputs, negated)` | 加门，`(x,y)` 是**输出**端口，返回全部端口 |
| `add_led(x, y)` | 加 LED |
| `add_wire(points)` | 折线布线（只能横平竖直） |
| `list_components()` | 列出元件和端口，方便改线 |
| `save_circuit(path)` | 写 `.circ` |
| `verify_circuit(path)` / `inspect_project(path)` | 按子电路检查悬空线头和局部物理网络多驱动；有 Tunnel/分线器限制 |
| `simulate_vectors(path, circuit, vectors_csv, image_path)` | 按 CSV 顺序驱动并检查实际 Logisim 仿真；可导出末状态 PNG |

设计上有一个刻意的取舍：**所有 add_* 都返回端口坐标**。模型不需要背几何表，
拿到 `ports` 直接连线就不会差一格——这是把"人类经验"塞进工具返回值里。

## 示例：74LS138 3-8 译码器

![decoder](assets/preview.png)

| 部分 | 实现 |
| --- | --- |
| 使能 | G1 先取反再进入反相输入；最终 `E=G1 & ~G2A_L & ~G2B_L` |
| 地址 | `A/B/C` 各一个非门，六根线做成竖直总线 |
| 译码 | 8 个 4 输入与非门，每门接三个地址位（原/反）+ 使能项 |
| 输出 | `Y0_L ~ Y7_L`，低有效 |

原理、真值表和级联扩展见 [docs/3-to-8-decoder.md](docs/3-to-8-decoder.md)。

## 原理

```
           ┌──────────────┐
Circuit ──▶│ to_xml()     │──▶ .circ ──▶ Logisim 打开
           └──────────────┘                    │
                   ▲                           │  Loader
                   │                           ▼
            几何表 / 切分                 LoadDump（Java）
                   │                           │
                   └──── 网络表 ◀──────────────┘
                          │
                dangling / conflicts
```

1. `Circuit` 只存元件和折线，不存"连接关系"；
2. 保存前在**每个端口和拐点处把线切开**，这样所有连接都是端点对端点，不依赖 Logisim 的 junction 自动修复；
3. `LoadDump` 用 Logisim 的 `Loader` 读回文件，打印元件、端口方向、导线；
4. Python 侧做并查集，检查悬空端点和多驱动网络。

## 已知的坑

这些是踩出来的，不是查文档查到的，全部整理在 [docs/pitfalls.md](docs/pitfalls.md)：
引脚 `tristate` 默认 true、总线没收在最后一个分支、反相圈让端口左移 10px、
斜线让 Logisim 加载时死循环、`lib` 索引不能省、门的 `size` 只接受 30/50……

## 路线图

- [x] `.circ` 生成 + 读回校验
- [x] MCP 工具集
- [x] 74LS138 示例
- [ ] 自动布局（网表 → 坐标）
- [x] 使用 CSV 对组合和时序电路执行 Logisim 仿真（其他 Logisim 版本兼容性待验证）
- [ ] 自动生成真值表与时序测试向量

## 许可

MIT
