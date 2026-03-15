import pytest
from soul_shell.engine.stream_parser import StreamParser


async def _stream(tokens: list[str]):
    for t in tokens:
        yield t


async def _collect(tokens: list[str]) -> tuple[str, list[str]]:
    parser = StreamParser()
    texts, cmds = [], []
    async for text, cmd in parser.feed(_stream(tokens)):
        texts.append(text)
        if cmd is not None:
            cmds.append(cmd)
    return "".join(texts), cmds


@pytest.mark.asyncio
async def test_no_cmd():
    text, cmds = await _collect(["hello ", "world"])
    assert text == "hello world"
    assert cmds == []


@pytest.mark.asyncio
async def test_single_cmd():
    text, cmds = await _collect(["执行 <cmd>ls -la</cmd> 看看"])
    assert text == "执行  看看"
    assert cmds == ["ls -la"]


@pytest.mark.asyncio
async def test_cmd_split_open_tag():
    """<cmd> 标签被切分到两个 chunk"""
    text, cmds = await _collect(["看看 <cm", "d>ls</cmd> 完成"])
    assert text == "看看  完成"
    assert cmds == ["ls"]


@pytest.mark.asyncio
async def test_cmd_split_close_tag():
    """</cmd> 标签被切分到两个 chunk"""
    text, cmds = await _collect(["<cmd>ls</", "cmd> ok"])
    assert text == " ok"
    assert cmds == ["ls"]


@pytest.mark.asyncio
async def test_cmd_split_across_three_chunks():
    """<cmd> 和 </cmd> 各自被切分"""
    tokens = ["好的 <cm", "d>ls -", "la</c", "md> 完成"]
    text, cmds = await _collect(tokens)
    assert text == "好的  完成"
    assert cmds == ["ls -la"]


@pytest.mark.asyncio
async def test_multiple_cmds():
    text, cmds = await _collect(["<cmd>ls</cmd> 然后 <cmd>pwd</cmd>"])
    assert cmds == ["ls", "pwd"]


@pytest.mark.asyncio
async def test_unclosed_cmd():
    """未闭合标签不触发命令，输出告警"""
    text, cmds = await _collect(["执行 <cmd>ls"])
    assert cmds == []
    assert "未闭合" in text or "丢弃" in text


@pytest.mark.asyncio
async def test_false_open_tag():
    """<cm 开头但不是 <cmd>，当普通文本处理"""
    text, cmds = await _collect(["这是 <color>红色</color> 文本"])
    assert cmds == []
    assert "<color>" in text


@pytest.mark.asyncio
async def test_empty_cmd():
    """空命令标签不触发"""
    text, cmds = await _collect(["<cmd>   </cmd>"])
    assert cmds == []


@pytest.mark.asyncio
async def test_cmd_with_whitespace_trimmed():
    """命令内容两端空白被 strip"""
    text, cmds = await _collect(["<cmd>  ls -la  </cmd>"])
    assert cmds == ["ls -la"]
