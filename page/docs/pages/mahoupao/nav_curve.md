# 净值曲线（Lightweight Charts）

该页面使用 `Lightweight Charts` 绘制回测策略净值曲线，并与 `CSI300` 同图对比。  
数据来源为项目根目录的 `backtest_csv/*.csv`，构建时会自动同步到站点的 `/backtest_csv/` 目录。

## 文件约定

- 文件名：`<topN>_<type>.csv`，例如 `10_ret.csv`、`20_filter_ret.csv`
- 关键字段：`date`、`strategy_equity`、`csi300_equity`
- 排序规则：先 `ret`，后 `filter_ret`；组内按 `topN` 从小到大

> 当前未检测到 backtest csv 文件。
