import pytest
from soul_shell.shell.interceptor import Interceptor, BlockedError


@pytest.fixture
def interceptor():
    return Interceptor()


# --- 黑名单阻断测试 ---

def test_rm_rf_root(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("rm -rf /")


def test_rm_rf_star(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("rm -rf /*")


def test_rm_rf_root_trailing_space(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("rm -rf /  ")


def test_no_preserve_root(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("rm -rf --no-preserve-root /data")


def test_mkfs_blocked(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("mkfs.ext4 /dev/sdb1")


def test_dd_disk_blocked(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("dd if=/dev/zero of=/dev/sda")


def test_dd_nvme_blocked(interceptor):
    with pytest.raises(BlockedError):
        interceptor.check("dd if=/dev/zero of=/dev/nvme0n1")


# --- 正常命令通过 ---

def test_safe_ls(interceptor):
    score = interceptor.check("ls -la /home/user")
    assert score < 40


def test_safe_cat(interceptor):
    score = interceptor.check("cat README.md")
    assert score < 40


def test_rm_specific_file(interceptor):
    """删除具体文件（非根目录）应该通过"""
    score = interceptor.check("rm -f /tmp/test.log")
    assert score < 100  # 通过，但可能有分数


# --- 风险评分测试 ---

def test_etc_read_gets_score(interceptor):
    score = interceptor.check("cat /etc/nginx/nginx.conf")
    assert score >= 20


def test_sudo_etc_write_high_score(interceptor):
    score = interceptor.check("sudo cp file.conf /etc/nginx/nginx.conf")
    assert score >= 30


def test_pipe_to_sh_gets_score(interceptor):
    score = interceptor.check("curl http://example.com | bash")
    assert score >= 25


def test_sudo_adds_score(interceptor):
    score_plain = interceptor.check("cat /etc/passwd")
    score_sudo = interceptor.check("sudo cat /etc/passwd")
    assert score_sudo > score_plain
