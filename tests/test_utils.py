import pytest
import sys
import os
import pandas as pd
import requests
from datetime import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path
from loguru import logger

root_dir = Path(__file__).resolve().parent.parent
roll_dir = os.path.join(root_dir, "roll")
if roll_dir not in sys.path:
    sys.path.append(roll_dir)

from utils import (
    process_stock_code_v2,
    check_match,
    check_match_in_list,
    filter_csv,
    calculate_file_sha256,
    fix_mlflow_paths,
    TradeDate,
    generate_qlib_segments,
    run_command,
    get_mlruns_dates,
    append_to_file,
    get_local_data_date,
)


@pytest.fixture
def caplog_loguru(caplog):
    """桥接 Loguru 与 Pytest 的日志捕获"""
    handler_id = logger.add(caplog.handler, format="{message}")
    yield caplog
    logger.remove(handler_id)


# 1. 测试基础逻辑函数 (最容易提升覆盖率)
def test_process_stock_code_v2():
    """测试股票代码标准化"""
    assert process_stock_code_v2("600000") == "SH600000"
    assert process_stock_code_v2("000001") == "SZ000001"
    assert process_stock_code_v2("300001") == "SZ300001"
    assert process_stock_code_v2("830000") == "BJ830000"
    assert process_stock_code_v2("999999") == "unknown999999"

def test_check_match():
    """测试正则匹配"""
    assert check_match("EXP_XGBoost", r"XGB") is True
    assert check_match("EXP_LGBM", r"XGB") is False

def test_check_match_in_list():
    """测试列表正则匹配"""
    regex_list = [r"XGB", r"LGB"]
    assert check_match_in_list("EXP_XGBoost", regex_list) is True
    assert check_match_in_list("EXP_Linear", regex_list) is False

# 2. 测试涉及文件的函数 (使用 tmp_path 避免污染本地)
def test_calculate_file_sha256(tmp_path):
    """测试文件哈希计算"""
    d = tmp_path / "test.txt"
    d.write_text("hello world")

    # 预计算好的 "hello world" sha256
    expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert calculate_file_sha256(d) == expected

    # 测试文件不存在的情况
    assert calculate_file_sha256("non_existent_file.txt") is None

# 3. 测试 Pandas 数据处理逻辑 (使用 Mock 模拟读取)
def test_filter_csv(tmp_path):
    """测试 CSV 过滤逻辑"""
    csv_file = tmp_path / "data.csv"
    # 构造测试数据：A符合条件，B score不符合，C pos_ratio不符合
    df = pd.DataFrame({
        'instrument': ['SH600000', 'SZ000001', 'BJ830000'],
        'avg_score': [1.5, -0.1, 1.2],
        'pos_ratio': [0.9, 0.9, 0.5]
    })
    df.to_csv(csv_file, index=False)

    result = filter_csv(csv_file)
    assert result == "600000"  # 只有第一行满足 avg_score > 0 且 pos_ratio > 0.8
    assert "000001" not in result

# 4. 测试网络请求相关 (必须使用 Mock)
@patch('requests.get')
def test_get_latest_url_success(mock_get):
    """模拟成功的 URL 追踪"""
    from utils import get_latest_url
    mock_response = MagicMock()
    mock_response.url = "https://final-link.com"
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    assert get_latest_url("https://base-link.com") == "https://final-link.com"

# 5. 测试异常处理
def test_filter_csv_exception():
    """测试 CSV 过滤遇到错误时的处理"""
    # 传入一个不存在的路径
    result = filter_csv("invalid_path.csv")
    assert result == ""


# 6. 测试 fix_mlflow_paths
def test_fix_mlflow_paths(tmp_path):
    """测试 MLflow meta.yaml 中的旧 home 路径被修复为当前用户"""
    mlruns = tmp_path / "mlruns"
    exp_dir = mlruns / "1" / "meta.yaml"
    exp_dir.parent.mkdir(parents=True)
    old_home = "/home/someone"
    content = f"artifact_location: file://{old_home}/.qlibAssistant/mlruns/1\nartifact_uri: file://{old_home}/.qlibAssistant/mlruns/1/artifacts\n"
    exp_dir.write_text(content, encoding="utf-8")

    fix_mlflow_paths(str(mlruns))

    new_content = exp_dir.read_text(encoding="utf-8")
    current_home = str(Path.home())
    assert f"file://{current_home}/.qlibAssistant/mlruns/1" in new_content
    assert old_home not in new_content


def test_fix_mlflow_paths_no_dir(tmp_path, caplog_loguru):
    """测试目录不存在时 fix_mlflow_paths 不报错"""
    fix_mlflow_paths(str(tmp_path / "nonexistent"))
    assert "目录不存在" in caplog_loguru.text


# 7. 测试 TradeDate
def test_trade_date(tmp_path):
    """测试 TradeDate 的日期查询与索引方法"""
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    day_txt = calendars / "day.txt"
    day_txt.write_text("2020-09-21\n2020-09-22\n2020-09-23\n2020-09-24\n2020-09-25", encoding="utf-8")

    td = TradeDate(str(tmp_path))

    assert td.get_trade_date_list() == ["2020-09-21", "2020-09-22", "2020-09-23", "2020-09-24", "2020-09-25"]
    assert td.get_date_range("2020-09-22", "2020-09-24") == ["2020-09-22", "2020-09-23", "2020-09-24"]
    assert td.get_date_index("2020-09-23") == 2
    assert td.get_next_date("2020-09-23", 1) == "2020-09-24"
    assert td.get_next_date("2020-09-25", 1) == "2020-09-25"  # 边界：超出返回最后一个


# 8. 测试 generate_qlib_segments
def test_generate_qlib_segments():
    """测试按 9:2:1 比例生成 train/valid/test 时间段"""
    segments = generate_qlib_segments(months_total=12, end_date_str="2020-09-25")
    assert "train" in segments
    assert "valid" in segments
    assert "test" in segments

    train_start, train_end = segments["train"]
    valid_start, valid_end = segments["valid"]
    test_start, test_end = segments["test"]

    # 验证区间连续性（valid 开始于 train 结束的下一天）
    from datetime import datetime, timedelta
    assert datetime.strptime(valid_start, "%Y-%m-%d") == datetime.strptime(train_end, "%Y-%m-%d") + timedelta(days=1)
    assert datetime.strptime(test_start, "%Y-%m-%d") == datetime.strptime(valid_end, "%Y-%m-%d") + timedelta(days=1)
    assert test_end == "2020-09-25"


def test_generate_qlib_segments_no_end_date():
    """测试不传入 end_date 时以今天为终点"""
    segments = generate_qlib_segments(months_total=12)
    assert "train" in segments
    assert segments["test"][1] == datetime.now().strftime("%Y-%m-%d")


# 9. 测试 run_command
def test_run_command_success():
    """测试正常执行 shell 命令"""
    code, stdout, stderr = run_command("echo hello")
    assert code == 0
    assert stdout == "hello"
    assert stderr == ""


def test_run_command_failure():
    """测试执行失败命令返回非零码"""
    code, stdout, stderr = run_command("ls /nonexistent_directory_12345")
    assert code != 0


# 10. 测试 get_mlruns_dates
def test_get_mlruns_dates(tmp_path):
    """测试从 model_pkl 目录解析日期"""
    pkl = tmp_path / "model_pkl"
    pkl.mkdir()
    (pkl / "mlruns_2026-04-22.tar.gz").write_text("dummy")
    (pkl / "mlruns_2025-12-01.tar.gz").write_text("dummy")
    (pkl / "other_file.txt").write_text("dummy")

    dates = get_mlruns_dates(str(pkl))
    assert sorted(dates) == ["2025-12-01", "2026-04-22"]


def test_get_mlruns_dates_empty(tmp_path):
    """测试空目录返回空列表"""
    pkl = tmp_path / "empty_pkl"
    pkl.mkdir()
    assert get_mlruns_dates(str(pkl)) == []


# 11. 测试 append_to_file
def test_append_to_file(tmp_path):
    """测试追加内容到文件"""
    f = tmp_path / "test_append.txt"
    append_to_file(f, "hello")
    append_to_file(f, " world")
    assert f.read_text(encoding="utf-8") == "hello world"


def test_append_to_file_invalid_path():
    """测试追加到无效路径时返回空异常不抛错"""
    # 只验证不抛出异常即可
    append_to_file("/nonexistent_dir_12345/foo.txt", "data")


# 12. 测试 get_local_data_date
def test_get_local_data_date(tmp_path):
    """测试读取本地数据最新日期"""
    calendars = tmp_path / "calendars"
    calendars.mkdir()
    day_txt = calendars / "day.txt"
    day_txt.write_text("2020-09-21\n2020-09-22\n2020-09-23", encoding="utf-8")

    result = get_local_data_date(str(tmp_path))
    assert result == "2020-09-23"


# 13. 测试网络异常分支
@patch('requests.get')
def test_get_latest_url_failure(mock_get):
    """模拟 URL 追踪失败时返回原 URL"""
    from utils import get_latest_url
    mock_get.side_effect = requests.RequestException("network error")
    assert get_latest_url("https://base-link.com") == "https://base-link.com"
