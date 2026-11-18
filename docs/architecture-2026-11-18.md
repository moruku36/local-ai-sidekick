# Architecture / 構成 — from 2026-11-18 (new PC)

[English overview](../README.md) | [日本語概要](../README.ja.md) | [Documentation index](README.md) | [Previous snapshot: 2026-11-06](architecture-2026-11-06.md)

## Scope and status / 位置づけと状態

This document describes the local configuration that takes over **from Wednesday, 2026-11-18**, when the new PC is delivered. Until then, the [2026-11-06 snapshot](architecture-2026-11-06.md) (RTX 3070 host) describes the local setup.

この文書は、新PCが届く **2026-11-18（水）以降** のローカル構成をまとめたものです。それまでは [2026-11-06 のスナップショット](architecture-2026-11-06.md)（RTX 3070 のホスト）が現行構成です。

**Status: delivered and measured (updated 2026-11-19).** The hardware below was delivered on 2026-11-18 (Dospara Toyama-Hongo, total ¥655,640 tax included, paid 2026-11-11). Strata 0.2.15 was installed the same night, and the Qwen3.8-Flash-Next configurations were measured on 2026-11-19; measured figures are marked as such below. The DeepSeek plan did not survive contact with the delivered machine — see the model operation table.

**状態：到着・実測済み（2026-11-19 更新）。** 下記ハードウェアは 2026-11-18 に到着しました（ドスパラ富山本郷店、税込 ¥655,640、2026-11-11 支払い完了）。Strata 0.2.15 は同日夜に導入し、Qwen3.8-Flash-Next の各構成は 2026-11-19 に実測しました。実測値はその旨を明記します。DeepSeek の計画は実機で成立しませんでした（モデル運用の表を参照）。

Sources: the PC order records summarized in the owner's PC purchase notes, and the Strata plan memo in [moruku36/Windows-Desktop-PC-Replace](https://github.com/moruku36/Windows-Desktop-PC-Replace) (`docs/strata-plan-20261111.md`, private repository).

根拠は、PC購入スペースにまとめた注文記録と、[moruku36/Windows-Desktop-PC-Replace](https://github.com/moruku36/Windows-Desktop-PC-Replace) の Strata 計画メモ（`docs/strata-plan-20261111.md`、非公開repo）です。

## Hardware / ハードウェア

| Component / 要素 | Specification / 仕様 |
| --- | --- |
| CPU | AMD Ryzen 7 9850X3D |
| Motherboard / マザーボード | ASUS TUF GAMING B850-PLUS WIFI |
| Memory / メモリ | CORSAIR DDR5-5600 64GB (32GB × 2, CMK64GX5M2D5600Z40) |
| GPU | PNY GeForce RTX 5070 Ti 16GB |
| Storage / SSD | ADATA XPG MARS 970 PLUS, M.2 Gen5, 2TB |
| PSU / 電源 | ASRock SL-1200P (1200W, 80+ Platinum) |
| Case / CPU cooler | Lian Li LANCOOL 217 / TRYX TURRIS T620 |
| OS | Windows 11 Pro |
| Peripherals / 周辺機器 | Logitech G502 HERO mouse, FIFINE AmpliGame AM8 microphone |

The old PC (Ryzen 7 5800X / RTX 3070 8GB / 32GB) stays in place until the new PC is verified working, and is then sold through a buyback service; it is not part of this configuration.

旧PC（Ryzen 7 5800X / RTX 3070 8GB / 32GB）は、新PCの動作確認が取れるまで残し、その後買取に出します。この構成には含めません。

## Architecture / アーキテクチャ図

```mermaid
flowchart TD
    U["User / human approval"] --> L["Lead AI (cloud): Claude / Gemini / ChatGPT — scope, design, review"]
    subgraph PC["New PC — from 2026-11-18 (Ryzen 7 9850X3D / RTX 5070 Ti 16GB / RAM 64GB / Gen5 SSD 2TB)"]
        L -->|"localhost API (OpenAI- / Anthropic-compatible)"| S["Strata: resident local LLM server"]
        S --> A["First / daily driver: Qwen3.8-Flash-Next IQ3_S (abliterated via control vector)"]
        S -. "switch, not simultaneous" .-> B["Heavy jobs: Qwen3.8-Flash-Next UD-Q4_K_XL (heavier quant, same model)"]
        A --> X["Expert placement (MoE)"]
        B --> X
        X --> G["Hot experts: GPU VRAM 16GB"]
        X --> M["Full expert set: RAM 64GB"]
        X --> D["Lookup tables: Gen5 SSD"]
        L -->|"file handoff .ai/TASK.md"| W["Sidekick Worker (this repository): Ollama-based roles"]
        W --> O["Local Ollama: explicitly selected installed model"]
    end
    W --> R[".ai/RESULT.md + diff"]
    R --> L
    Old["Old PC (RTX 3070)"] -. "retired after the new PC is verified; buyback planned" .-> X
    S -->|"tailnet only, via Tailscale Serve"| K["HomeLab machine (Mac mini / OpenClaw): API client"]
```

Reading the diagram / 図の読み方:

- **Strata is the new local LLM platform.** It is a model-specific inference engine for the Qwen3.8-Flash-Next MoE (125B total parameters, ~6B active per token, 24,576 experts of which 10 activate per token). Frequently used experts sit in GPU VRAM, the full expert set in RAM, and lookup tables on SSD. It serves OpenAI-compatible and Anthropic-compatible APIs on localhost, so coding agents can connect to it.
- **Strata は新しいローカルLLM基盤です。** Qwen3.8-Flash-Next（125B の MoE、トークンごとに約6Bが活性化、エキスパート24,576個のうち10個を使用）に特化した推論エンジンで、使用頻度の高いエキスパートを GPU、全体を RAM、参照テーブルを SSD に分散配置します。OpenAI互換・Anthropic互換 API を localhost で提供し、コーディングエージェントから接続できます。
- **Models run one at a time.** The operating policy is: Qwen3.8-Flash-Next IQ3_S for daily use, the heavier UD-Q4_K_XL quant of the same model for heavy jobs, never both at once. Both configurations are saved as named configs, and switching across restarts was verified on 2026-11-19.
- **モデルは片方ずつ運用します。** 普段使いは Qwen3.8-Flash-Next IQ3_S、重い処理は同じモデルの重い量子化 UD-Q4_K_XL、同時には動かしません。両構成とも名前付き設定として保存し、再起動をまたいだ切り替えを 2026-11-19 に確認しました。
- **The Sidekick Worker in this repository is unchanged.** Its implemented path still talks to Ollama (see the [2026-11-06 snapshot](architecture-2026-11-06.md)). A native Sidekick↔Strata adapter does not exist in this repository, and the explicit model roles still validate a loopback Ollama endpoint; treat any connection through Strata's compatible API surface as unverified until it is exercised and recorded.
- **このrepoの Sidekick Worker 自体は従来どおりです。** 実装済みの経路は Ollama を使います（[2026-11-06 のスナップショット](architecture-2026-11-06.md)）。Sidekick と Strata をつなぐ専用アダプタはこのrepoにはなく、明示ロールの検証対象も loopback の Ollama エンドポイントのままです。Strata の互換 API 経由の接続は、実際に試して記録するまで未検証として扱います。
- **Loading is heavy, so Strata is a resident server.** Startup reads roughly 35–55GB (cold start takes minutes), and requests are served one at a time by default. It is not a per-request launch tool.
- **読み込みが重いため、Strata は常駐サーバー前提です。** 起動時に約35〜55GBを読み込み、コールドスタートには数分かかります。既定では同時リクエストは1つずつ処理します。
- **API reach.** Strata listens on localhost. Since 2026-11-19 it is also reachable from the owner's home-lab machine (Mac mini) over the tailnet only, via Tailscale Serve; reachability from the Mac mini was verified. It is not exposed to the LAN or the Internet.
- **API の到達範囲。** Strata の待ち受けは localhost です。2026-11-19 から、所有者のホームラボ機（Mac mini）からのみ、Tailscale Serve 経由で tailnet 内に限り到達可能にし、Mac mini からの接続を確認しました。LAN やインターネットへは公開していません。

## Model operation / モデル運用

| Role / 役割 | Model / モデル | Notes / 備考 |
| --- | --- | --- |
| First model (decided 2026-11-18, revised the same day) / 第一弾モデル（2026-11-18 決定・同日改訂） | Qwen3.8-Flash-Next IQ3_S on Strata, abliterated via control vector: ISTA-DASLab GSQ-RCO IQ3_S (stock weights, byte-identical) + the refusal-direction vector extracted from huihui-ai's abliterated build, applied at runtime with Strata's `--control-vector-scaled` | Meets both of the owner's requirements: the best model this hardware can run, in abliterated (uncensored) form. IQ3_S needs ~54.8GB of RAM+VRAM combined and fits the 64GB RAM + 16GB VRAM. The weights stay stock; the abliteration is a runtime projection, which differs slightly from a baked-in weight edit (for example, layer 0 cannot be steered). Abliterated — handle with care |
| Daily driver / 普段使い | Qwen3.8-Flash-Next IQ3_S (on Strata) — the first model above / 第一弾と同一 | **Measured 2026-11-19:** 37.4–47.9 tok/s in short generation tests; 39.36 tok/s average in the 10-task hard bench (see the results note below). VRAM ~14.1 GiB, engine RAM ~21.5 GiB. Restart-to-responsive 49.5 s with cache (not a true cold start) |
| Heavy jobs / 重い処理 | Qwen3.8-Flash-Next UD-Q4_K_XL (on Strata), same control vector | **Measured 2026-11-19:** 111.3GB, hash-verified. About half the speed of IQ3_S (19.82 tok/s average in the hard bench). Role: re-attempts of tasks IQ3_S fails, and cross-checking important outputs — see the results note below |
| Not available / 利用不可 | DeepSeek V4.1-Flash (on Strata) | Strata 0.2.15 no longer lists DeepSeek models (last listed in 0.2.13). A side-by-side legacy install was investigated on 2026-11-19, but the legacy version shares config/component storage with the current install and isolation could not be confirmed, so it is **on hold** rather than installed. The owner keeps Strata at the latest version |
| Alternative route / 代替ルート | Huihui-Qwen3.8-Flash-Next-abliterated-v2-GGUF (baked-in abliteration) | Fallback if the control-vector route misbehaves: load as a local GGUF in Strata (own-GGUF import; a manual repack with the bundled `tools/iq_pack.py` may be needed), or run on llama.cpp. Abliterated — handle with care |
| Dropped (2026-11-18) / 不採用（2026-11-18） | Huihui-Qwen3.8-27B-abliterated-GGUF on llama.cpp | Considered first for its ecosystem (see the decision note below), then dropped the same day: Strata does not support dense models (the author marks them out of scope and points to llama.cpp), and the owner's requirements are met better by Flash-Next on Strata |

**Decision (2026-11-18, revised the same evening): install Strata with the abliterated Qwen3.8-Flash-Next first; the 27B is dropped.** The morning's first decision was the abliterated Qwen3.8-27B on llama.cpp, because the 27B is the centre of the Qwen3.8 ecosystem on Hugging Face (official Qwen/Qwen3.8-27B: 20,424 likes; unsloth GGUF build ~6.8M downloads; derivative work such as the Pi Harness Adapter LoRA also targets the 27B). Two checks later that day reversed it: (1) Strata is an MoE-only engine and its author marks dense models out of scope, so the 27B could never use the new PC's Strata platform; (2) Flash-Next can be abliterated on Strata after all — the community publishes ISTA-DASLab's stock GSQ-RCO weights together with a refusal-direction control vector extracted from huihui-ai's abliterated build, and Strata applies it at runtime. The owner's requirements — the best model this hardware can run, in abliterated form — are therefore met by Flash-Next IQ3_S on Strata, a 125B-class model instead of a 27B. Order: install Strata + Flash-Next IQ3_S + control vector, measure, then DeepSeek for heavy jobs. (The DeepSeek step was superseded on 2026-11-19 — see the measured results note below.)

**決定（2026-11-18・同日夜に改訂）：第一弾は Strata ＋ Qwen3.8-Flash-Next の abliterated 構成とし、27B は不採用とする。** 当初の決定は、27B が Qwen3.8 エコシステムの中心であること（公式 Qwen/Qwen3.8-27B の likes 20,424、unsloth GGUF 版は約683万ダウンロード、Pi 向け Harness Adapter のような派生も 27B 対象）を理由に、llama.cpp 上の Qwen3.8-27B abliterated でした。同日中に確認した2点で覆りました。(1) Strata は MoE 専用エンジンで、作者自身が dense モデルを対象外としているため、27B では新PCの Strata 基盤を使えない。(2) Flash-Next は Strata 上で abliterated 化できた（ISTA-DASLab の純正 GSQ-RCO 重み＋huihui-ai の abliterated 版から抽出した拒否方向コントロールベクターを、Strata の機能で実行時に適用する構成がコミュニティから公開されている）。所有者の要件「このスペックで動かせる一番いいモデルを、abliterated で」は、27B ではなく 125B 級の Flash-Next IQ3_S（Strata）で満たされます。順序は「Strata ＋ Flash-Next IQ3_S ＋ コントロールベクターを導入 → 実測 → 重い処理は DeepSeek」とします。（DeepSeek の段は 2026-11-19 に差し替え。下記の実測結果を参照）

**Measured results (2026-11-19).** Strata 0.2.15 + Flash-Next IQ3_S + control vector installed and verified (hash-checked; vector application confirmed in logs; API on localhost). UD-Q4_K_XL was then added as the heavy configuration. A 10-task hard bench (math, coding with unit tests, logic, instruction following; variants of public problems; 3 trials per task per config, temperature 0.6, auto-graded) scored **IQ3_S 7.0/10 vs UD-Q4_K_XL 7.67/10** — the entire difference came from one combinatorics problem (IQ3_S 1/3 trials correct, Q4 3/3); the other nine tasks scored identically. Conclusion: IQ3_S stays the daily driver; Q4 is the fallback for tasks IQ3_S fails and for verifying important outputs. The abliteration effect itself is still **undetermined**: the stock model did not refuse the harmless test questions even without the vector, so no judgement was possible.

**実測結果（2026-11-19）。** Strata 0.2.15 ＋ Flash-Next IQ3_S ＋ コントロールベクターを導入・確認（ハッシュ照合、ベクター適用をログで確認、API は localhost）。続いて重い構成として UD-Q4_K_XL を追加した。難問ベンチ（数学・単体テスト付きコーディング・論理・指示追従の全10問、公開問題の変種、各構成3回試行、temperature 0.6、自動採点）では **IQ3_S 7.0/10 対 UD-Q4_K_XL 7.67/10** で、差は数え上げ1問のみ（IQ3_S は3回中1回、Q4 は3回とも正解）、残り9問は同一結果だった。結論として、常用は IQ3_S のままとし、Q4 は IQ3_S が落とす課題への再挑戦と重要出力の検証用とする。なお abliteration の効果自体は **未判定**（無害なテスト質問はベクターなしでも拒否されず、判定材料が得られなかった）。

Quantization references for Qwen3.8-Flash-Next on Strata (vendor figures, RTX 5070 12GB): Q2_0 ≈ 94 tok/s (66GB download, ~40GB RAM), IQ2_XS ≈ 79 tok/s (68GB, ~42GB RAM), IQ3_XXS ≈ 62 tok/s (76GB, ~49GB RAM). With 64GB RAM, the full expert set fits in memory; the RTX 5070 Ti's 16GB VRAM holds more hot experts than the 12GB reference machine, so equal or better speed is expected — as an expectation, not a result.

Vendor benchmark context (Qwen's self-measured figures for the full-precision model): SWE-bench Pro 62.5, GPQA Diamond 91.7, LiveCodeBench v6 91.9. These are not same-condition comparisons, and a ~3-bit quantization should be discounted from the published full-precision numbers.

## Changes from the 2026-11-06 snapshot / 11月6日版からの変更

| Area / 項目 | Until 2026-11-17 | From 2026-11-18 |
| --- | --- | --- |
| GPU | RTX 3070 (8GB) | RTX 5070 Ti (16GB) |
| Memory / メモリ | 32GB | 64GB (DDR5-5600, 32GB × 2) |
| Local LLM platform / 基盤 | Ollama with a single selected model | Strata added for the large MoE models; Ollama path for the Sidekick Worker remains |
| Local model status / モデル | Qwen retired; successor undecided | Qwen3.8-Flash-Next IQ3_S (daily) / UD-Q4_K_XL (heavy), one at a time — measured 2026-11-19. DeepSeek not available on Strata 0.2.15 (on hold) |
| Old PC / 旧PC | Main host | Retired after verification; buyback planned |

## Verification after delivery / 到着後の確認

Before any item above is described as operational, record on the delivered machine:

実機で「運用中」と書けるようにするには、到着後に次を記録します。

1. ✅ Strata installation and version — Strata 0.2.15, installed 2026-11-18 / Strata の導入とバージョン（0.2.15、2026-11-18 導入済み）
2. ✅/⏳ Qwen3.8-Flash-Next IQ3_S with the refusal-direction control vector: measured (see the results note above). The abliteration-effect check is still open — the stock model did not refuse the harmless probes, so the effect is undetermined / 実測済み。abliteration の効果判定のみ未了（無害な質問では純正モデルも拒否せず、判定できていない）
3. ✅ Heavy configuration: DeepSeek was replaced by UD-Q4_K_XL of the same model and measured (see above). DeepSeek itself is not supported on Strata 0.2.15; the legacy side-by-side route is on hold / 重い構成は UD-Q4_K_XL で実測済み。DeepSeek は 0.2.15 の対応外で、旧版併設は保留
4. ⏳ Whether the baked-in Huihui abliterated GGUF route is needed as a fallback — not needed so far; the control-vector route is in service / 焼き込み型ルートの要否（現時点では不要。ベクター方式で稼働中）
5. ✅ Update this document with the measured values and dates — done 2026-11-19 / この文書へ実測値と日付を反映（2026-11-19 実施）

## Boundaries / 境界

- Strata's APIs listen on localhost. The single exception, added 2026-11-19, is tailnet-only access from the owner's home-lab machine via Tailscale Serve. This document does not authorize exposing them to a LAN or the Internet (no Tailscale Funnel).
- Strata の API の待ち受けは localhost です。唯一の例外として、2026-11-19 に所有者のホームラボ機からのみ Tailscale Serve 経由の tailnet 内アクセスを加えました。LAN やインターネットへの公開（Tailscale Funnel 含む）を認める文書ではありません。
- HomeLab / OpenClaw remain separate systems, as in the previous snapshot.
- HomeLab / OpenClaw は、従来どおり別システムです。
- No private IPs, machine names or account identifiers are published here.
- プライベートIP、実ホスト名、アカウント識別子は公開しません。
