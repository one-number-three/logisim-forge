# 踩坑记

这份文档记录做这个项目时**真实撞上的**问题。Logisim 的特点是：写错了不报错，
只是静静地画错。下面每条都给出症状、原因、修法。

---

## 1. 总线没有收在最后一个分支 → "线是断的"

**症状**：电路逻辑上没错，但每根竖直总线的下端都比最后一个分支多出一截，
悬在空中，看起来像被剪断的线头。人一眼就会问"这里是不是断了"。

**原因**：图省事把所有总线都画到同一个 `y = BOTTOM`：

```python
route((x, top), (x, 1040))    # 所有总线都到 1040
```

但每个信号最后一次被用到的高度不同（`A` 可能用到第 7 行，`A'` 只用到第 6 行），
多出来的部分就是悬空线。

**修法**：先收集每个信号要接的全部行号，再让总线停在自己的最后一个分支上：

```python
taps = {name: [] for name in BUS}
for i, y in enumerate(ys):
    for k, b in enumerate(bits):
        taps[signal_name].append(y + OFF[k])

for name, x in BUS.items():
    route((x, SRC_Y[name]), (x, max(taps[name])))
```

**自查**：`verify_circuit()` 返回的 `dangling` 就是这类端点，必须为空。

---

## 2. 反相圈会让那个输入端口再往左挪 10px

**症状**：3 输入与门，输入端口本应在 `x-50`，但其中两个输入画了反相圈后，
线接在 `x-50` 却连不上，`dangling` 报出那两个点。

**原因**：反相圈（bubble）画在门体外面，**有圈的那个输入端口整体左移 10px**：

```
AND Gate loc=(420,100) bound_boxes=(360,75) 60x50
   port (420,100)   <- 输出
   port (370,80)    <- 输入0，没有圈 -> 420-50
   port (360,100)   <- 输入1，有圈   -> 420-60
   port (360,120)   <- 输入2，有圈   -> 420-60
```

所以门的左边不是一条直线。几何表必须按"每个输入是否取反"分别算偏移：

```python
def gate_inputs(kind, loc, inputs, negated=()):
    base = NAND_BODY_W if kind == "NAND Gate" else AND_BODY_W
    return [(loc[0] - base - (10 if i in negated else 0), loc[1] + d)
            for i, d in enumerate(GATE_PORT_DY[inputs])]
```

**教训**：只检查"线的端点连到了哪个信号"是不够的——线可以连到另一根线，
但那根线根本没碰到端口。必须拿**端口坐标**和**导线端点**比对，这正是
`verify_circuit()` 做的事。

---

## 3. 引脚 `tristate` 默认是 true（ITA 版）

**症状**：整个电路所有线都是蓝的/红的，引脚上显示 `x`，门输出一片红（error）。

**原因**：Logisim-ITA 新建引脚时 `tristate` 默认为 **true**，引脚处于高阻态，
不驱动任何值；门看到悬空输入就输出 error。

**修法**：生成时显式写死：

```xml
<a name="tristate" val="false"/>
```

---

## 4. 引脚方向：`output` 属性是反直觉的

**症状**：输出端和门输出接到同一根线上，整条线变红（多驱动短路）。

**原因**：`.circ` 里的属性叫 `output`，但含义是"这个引脚是不是**输出引脚**"：

| 想要 | XML | 端口方向 |
| --- | --- | --- |
| 输入引脚（驱动电路） | `output=false` | `out=true` |
| 输出引脚（显示结果） | `output=true` | `in=true` |

设反了就是两个驱动短接，Logisim 直接画红。

---

## 5. 斜线会让 Logisim 加载时死循环

**症状**：打开文件时卡死，Java 抛 `OutOfMemoryError`，栈顶在
`WireRepair.doOverlaps`。

**原因**：Logisim 的导线只能横平竖直。写一根斜线（哪怕只有 1px），
加载时的重叠修复会陷入死循环并吃光堆内存。

**修法**：布线时强制校验：

```python
if a[0] != b[0] and a[1] != b[1]:
    raise ValueError("diagonal segment: Logisim hangs on those")
```

---

## 6. 端口坐标不是元件坐标

| 元件 | `loc` 是什么 | 输入端口 |
| --- | --- | --- |
| Pin | 唯一的端口 | — |
| LED | 输入端口 | — |
| NOT | 输出端口 | `loc.x - 30` |
| AND | 输出端口 | `loc.x - 50`，y 偏移见下表 |
| NAND | 输出端口 | `loc.x - 60`（多 10px 画圈） |

输入 y 偏移（相对 `loc.y`）：

| 输入数 | 偏移 |
| --- | --- |
| 2 | -20, +20 |
| 3 | -20, 0, +20 |
| 4 | -20, -10, +10, +20 |
| 5 | -20, -10, 0, +10, +20 |
| 8 | -40, -30, -20, -10, +10, +20, +30, +40 |

注意偶数个输入会**跳过中心行**，所以间距不一定是 10 的整数倍关系。

---

## 7. 交叉不等于连接，端点落在线上才连接

- 两根线十字交叉：**不通**（Logisim 不会自动加结点）
- 一根线的**端点**落在另一根线中间：**通**（Logisim 自动补 junction 点）
- 端点对端点：**通**

所以生成器在保存前会把每根线在"端口 / 拐点"处切开（`Circuit._split_wires`），
让所有连接都退化成"端点对端点"，完全不依赖 Logisim 的自动修复。

---

## 8. 元件必须写 `lib` 索引

**症状**：加载成功但元件全部消失，控制台打印
`组件 `AND Gate' 未找到 [main.AND Gate((300,110))]`。

**原因**：`<comp>` 没有 `lib` 属性时，Logisim 只在"当前库"里找，找不到就丢弃。

**修法**：`<lib desc="#Gates" name="1"/>` 声明库，元件写 `lib="1"`。
本项目的库索引固定为：0 = Wiring（Pin、Splitter）、1 = Gates、2 = I/O（LED、七段数码管）。

---

## 9. 门的 `size` 不能随便填

**症状**：`attribute value (40) is not valid for size`。

**原因**：门只接受特定尺寸（30/50 等）。**不写 `size` 就用默认 50**，别自己发明。

---

## 10. 坐标必须落在 10px 网格上

Logisim 内部按 10px 吸附。写 `(105, 60)` 不会报错，但端口在 110，线画到 105 就差 5px。

---

## 11. 只检查 XML 不算验证

**症状**：XML 格式合法、Logisim 能打开、图看起来也对，但仿真时某个门输入是悬空的。

**原因**：连接性是**几何**关系，不是 XML 结构关系。`<wire>` 写得再合法，
端点没碰到端口就是没连。

**修法**：用 Logisim 自己的 `Loader` 读回文件，拿到端口坐标和实际导线，再做并查集。
本项目的 `logisim_forge/verify.py` 干的就是这件事。

---

## 12. 在沙箱 / CI 里启动 Logisim

- **注册表**：Java 的 `java.util.prefs` 在 Windows 上写注册表，沙箱/CI 里会被拒绝，
  Logisim 直接 `ExceptionInInitializerError`。解决：自带一个内存版 `PreferencesFactory`
  （`logisim_forge/java/MemPrefs*.java`），用 `-Djava.util.prefs.PreferencesFactory=MemPrefsFactory`
  启动。
- **自动更新弹窗**：ITA 版启动会连服务器查新版本，联网时会弹窗挡住主窗口。
  解决：把 HTTP 代理指向一个黑洞端口（`-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=9`），
  让它快速失败并跳过。
- **类路径**：`MemPrefsFactory` 必须真的在 `-cp` 里，否则第一次启动就崩（这个坑也踩过）。

---

## 13. 别用截图颜色判断对错

用 `PrintWindow` 抓 Java 窗口时，可能拿到**尚未重绘**的一帧：整片线都是蓝的，
看起来像全悬空。截图只用来检查版式，正确性交给 `verify_circuit()`。

---

## 14. 空的 `<lib>` 会被 Logisim 丢掉——表现是“没有基础库、没有工具、元件拖不动”

**症状**：打开生成的 `.circ`，左侧树里没有「基础库 (Base)」，工具条只有“添加/上移/下移/删除电路”，
画布上的元件选不中、拖不动。新建一个空工程则一切正常。

**原因**：为了省事写成自闭合的空元素

```xml
<lib desc="#Base" name="0"/>
```

Logisim 加载时会把**没有子元素的库丢掉**。Base 库一没，`Poke / Select / Text` 这些编辑工具就都没了——
于是没有工具栏、也没法框选。文件本身没错，是“少了内容”。

**修法**：给 Base 库写上 Logisim 自己会写的那个子元素：

```xml
<lib desc="#Base" name="0">
  <tool name="Text Tool">
    <a name="text" val=""/>
    <a name="font" val="Dialog plain 12"/>
    <a name="color" val="#000000"/>
    <a name="halign" val="center"/>
    <a name="valign" val="base"/>
  </tool>
</lib>
```

**更稳的修法**：生成完让 **Logisim 自己再存一遍**（load → save 往返），产物就是它亲手写的格式：

```python
circuit.save(path)
normalize(path)      # 内部调用 logisim_forge/java/SaveAs.java
```

`examples/74ls138.py` 现在就是这么做的。往返之后 `source` 变成真实版本号，Base 库带上 Text Tool，
树里能看到「基础库 (Base) → 戳工具 / 编辑工具 / 选择工具 / 连线工具 / 文本工具」。

### 14b. 工具条的内容也存在文件里：`<toolbar>`

补上 Base 库之后，树里能看到「基础库 → 戳工具/编辑工具…」，但**工具条上仍然没有按钮**。
原因是工具条（那一排手、箭头、引脚、非门…）是 `<toolbar>` 元素写死在 `.circ` 里的，不是偏好设置：

```xml
<toolbar>
  <tool lib="0" name="Poke Tool"/>
  <tool lib="0" name="Edit Tool"/>
  <sep/>
  <tool lib="1" name="Pin"><a name="tristate" val="false"/></tool>
  <tool lib="1" name="Pin"><a name="facing" val="west"/><a name="output" val="true"/></tool>
  <tool lib="2" name="NOT Gate"/>
  <tool lib="2" name="AND Gate"/>
</toolbar>
```

没有这一段，Logisim 就当“这个工程本来就没有工具”，打开后工具条空着，元件也拖不动。
连同 `<mappings>`（鼠标键绑定）和 `<options>`（gateUndefined / simlimit / simrand）一起写全，
生成的文件就和 Logisim 自己保存的一模一样了。
