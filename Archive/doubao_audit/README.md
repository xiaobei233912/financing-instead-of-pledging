# 豆包融资 PAL 报告审核

先读 [审核验证报告](D:/codex/融资/Archive/doubao_audit/审核验证报告.md)。长期单利挂息是主研究设定；按月付息仅作另一种合同条件下的对照。

## 文件与范围

- `source/`：从用户指定的 `D:\临时\豆包\融资` 只读复制的原始文件。外部工作区不修改、不在其中执行程序。
- `audit_original.py`：在本项目副本上复现原结果，并记录新融资保证金缺口及负本金等证据。
- `corrected_variants.py`：逐项会计修正，保留原模型其他简化，用于解释差异。
- `gated_engine.py`：依赖父目录的逐笔账户内核 `backtest.py`，实现压力准入、runway、单利挂息、可选月付息、交收、展期及再平衡。
- `run_validation.py`：运行 810 个预定场景，保存结果和主路径日账。用 6 个本地计算进程，无代理调用、无联网交易。
- `ideal_benchmark.py`：同日历及启动消费的理想 PAL 单利挂息/按月资本化对照。
- `inspect_paths.py`：观察未完成再平衡、还款和现金库存，并比较副本与外部原件的 SHA-256。
- `output/`：实际计算结果，不需要重新下载数据即可复现。

## 策略名称

| 名称 | 利息 | 信用账户卖券还款 |
| --- | --- | --- |
| A | 无融资 | 无 |
| D_hold | 单利长期挂账 | 禁止；必须偿还时明确停止 |
| D_hang | 平时单利长期挂账 | 调仓/退出时允许，复借需另过保证金和压力检查 |
| D_pay | 每月支付 | 允许 |
| D_refinance | 每月支付后，另申请现金资产融资替代所售资产 | 允许，申请可能失败 |

`pay_monthly_interest=False` 为默认值。`never_repay=True` 启用零还本、零付息分支；与月付息设置互斥。`rebal_calendar='yearend'` 采用年末再平衡、入场周年生活费；`'252'` 沿用豆包每 252 个交易日的两项安排。每个已保存结果都包含完整配置。

## 复现命令

在 `D:\codex\融资` 执行。操作模型只依赖 Python 标准库。

```powershell
python -m unittest test_backtest -v
python -m unittest discover -s doubao_audit -p 'test_*.py' -v
python doubao_audit\run_validation.py
python doubao_audit\ideal_benchmark.py
python doubao_audit\inspect_paths.py
python doubao_audit\verify_audit.py
python doubao_audit\build_audit_report.py
```

原代码使用 pandas、numpy。若要重新生成原结果审计和修订梯级，可使用已安装的完整 Python 运行环境：

```powershell
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' doubao_audit\audit_original.py
& 'C:\Users\admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' doubao_audit\corrected_variants.py
```

原副本审计输出沿用 Python JSON 的 NaN/Infinity 表示无债务时的无定义值；正式操作模型输出使用标准 JSON null。原模型归一化金额为初始资产=1，操作模型为初始 1,000,000 元；报告均换算为万元，不可把两类原始数字直接相减。

## 解释边界

基础模型允许半年展期时继续挂息，续约最低维持率设为 200%；这些是待实际合同核实的条件。单利计算、到期可展期，不自动证明允许长期不支付利息。未付息不自动滚入本金；只有真实还款后再融资，才可能产生经济上的利息资本化。

runway 指普通账户全部资产市值/年生活费，包括股票；不保证普通现金库存大于零。纯零偿还分支可能无法完成年末 70/30，因此“没有两类破产”不能代表同时满足全部配置要求。详细冲突与反例见报告。
