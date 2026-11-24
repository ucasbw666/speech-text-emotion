# ChineseASR 开发计划

状态：`[x]` 已完成，`[~]` 进行中，`[ ]` 未开始，`[!]` 阻塞或需要复核。

- [x] Phase 1 环境检查
  - 记录 OS、Python/Conda、GPU/CUDA/cuDNN、磁盘空间。
  - 根据本机 8 GB 显存选择 Whisper-small 主路线。
  - 建立工程目录、依赖说明和可复现配置。
- [x] Phase 2 Baseline
  - 实现本地模型下载、离线加载和单文件中文推理。
  - 先用小样本完成最小推理 smoke test。
- [x] Phase 3 数据集
  - 支持公开普通话数据集及用户自备目录。
  - 生成 train/dev/test JSONL manifest 和数据统计。
- [x] Phase 4 Evaluation
  - 实现字符级 Levenshtein、S/D/I、CER 和批量评估。
  - 保存逐样本预测及汇总结果。
- [x] Phase 5 Fine-tuning
  - 小数据 smoke test 后再执行参数高效微调。
  - 保存配置、日志和最佳 checkpoint。
- [x] Phase 6 Improvement
  - 比较三类候选方案，优先验证轻量数据增强。
  - 仅按真实 test CER 判断是否有效并完成消融/错误分析。
- [x] Phase 7 UI
  - Gradio 本地 Web UI，支持上传和麦克风。
  - 显示文本、时长、耗时、设备和模型模式。
- [x] Phase 8 Report
  - 完成 README、方法说明、答辩指南和实验报告。
  - 图表只使用实际生成的实验数据。
- [x] Phase 9 Final Verification
  - 执行测试与端到端验收，生成 FINAL_CHECKLIST.md。
  - 整理 submission，避免重复复制大数据和模型。

## 当前技术决策

- 主模型：`openai/whisper-small`。
- Baseline：未经本数据集微调的预训练 Whisper-small，固定中文转写任务。
- 训练方案：8 GB GPU 下使用 fp16、梯度检查点、batch size 1 和梯度累积；优先 LoRA/参数高效微调。
- 首选改进：训练时 speed perturbation、random gain、background noise 与 SpecAugment 的可配置组合。
- 数据管理：音频不复制，通过绝对/相对路径 JSONL manifest 管理。
- 真实性规则：未运行的结果统一标为 `Pending Experiment`，禁止填写示例数字冒充实验结果。

## 风险与缓解

- C 盘仅约 18 GB 可用：只下载一个主模型，数据集优先使用可控子集；大数据建议放 D/E 盘。
- 当前 `python`/`pip` 命令指向不可用的 Microsoft Store alias：统一使用专用 Conda 环境或 `conda run -n chinese-asr ...`。
- 完整 AISHELL-1 体积较大：代码兼容官方划分，但先以可复现小子集贯通流程。
- 8 GB 显存不足以常规全参数训练 Whisper-small：使用参数高效微调和梯度累积，先 smoke test。

