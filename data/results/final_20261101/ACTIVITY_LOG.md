# Final study activity log (started 2026-11-01)

2026-11-01T10:14:12.4544375Z  START cal_l120,cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40 design sha256 
2026-11-01T10:14:12.7262772Z  cal_l120,cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40 preflight below 0.8 GB (rc=1): running anyway; the runner enforces the design's own rule per block
2026-11-01T10:14:13.2161560Z  FINISHED cal_l120,cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40 exit=1
2026-11-01T10:14:13.2181666Z  ALLDONE cal_l120,cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40

2026-11-01T10:40:16.0620422Z  NOTE: the first launch used a malformed -Designs argument (one string) and did nothing (no session created). Free RAM was 0.4 to 0.8 GB (rsEngineSvc 5.7 GB working set; earlier sessions had 2.4 to 3.0 GB at run start). Script rewritten to wait for >= 2.0 GB before each attempt and to retry under new session ids; the design rule min_free_ram_gb 0.8 is unchanged.
2026-11-01T11:14:50.6425773Z  NOTE: waiter restarted with StartGB 2.4 (earlier sessions: 4.15 GB free at session start, 2.78 GB once the pool was alive => the pool costs about 1.4 GB; block rule needs 0.8 GB left).
2026-11-01T11:26:50.1281834Z  Detached waiter replaced by scripts/final_stage1.ps1 (same wait/retry rule: StartGB 2.4).
2026-11-01T12:09:48.8309206Z  PAUSED by the user's request (security-software change, possible Windows restart). Pipeline task bt09qtu1g (final_stage1.ps1) stopped via the harness; it had started no session. Checkpoint checkpoint_20261101T120846Z (zip sha256 4CFB8013EA7D317CC7C60D4E0869EB567B6422B404ED2F2EAC17476A372F71DB). Resume steps: RESUME.md. Nothing deleted or overwritten.
2026-11-01T12:35:58.2843818Z  RESUMED at the user's request: RAV Endpoint Protection uninstalled, Defender active, available RAM 3.38 GB (threshold 2.4 GB unchanged, design rule 0.8 GB per block unchanged). Code verified identical to checkpoint (48 of 49 hashes equal; the 49th is this log). Readiness: 80 tests passed (final-study, coordinator, study2 incl. CUDA, analysis). Memory monitor started: data\results\final_20261101\memory_monitor.csv. Stage 1 relaunched (idempotent).
2026-11-01T12:41:34.7120722Z  START cal_l120 design sha256 9542DB55507CC66B4CF0E086C86958BD11633DBB7FD649AC1EAEB1E6B38AFB11 free 2.47 GB
2026-11-01T12:50:05.1847243Z  FINISHED cal_l120 exit=2 status=aborted
2026-11-01T12:51:05.8955213Z  START cal_l120_r2 design sha256 9542DB55507CC66B4CF0E086C86958BD11633DBB7FD649AC1EAEB1E6B38AFB11 free 2.51 GB
2026-11-01T13:00:22.2497250Z  FINISHED cal_l120_r2 exit=0 status=complete
2026-11-01T13:01:22.8953232Z  START cal_l40 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 3.53 GB
2026-11-01T13:04:08.5449247Z  FINISHED cal_l40 exit=2 status=aborted
2026-11-01T13:05:09.6336311Z  START cal_l40_r2 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.82 GB
2026-11-01T13:05:16.0610021Z  FINISHED cal_l40_r2 exit=2 status=aborted
2026-11-01T13:06:16.8221339Z  START cal_l40_r3 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 3.21 GB
2026-11-01T13:06:21.0988139Z  FINISHED cal_l40_r3 exit=2 status=aborted
2026-11-01T13:07:21.7923717Z  START cal_l40_r4 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.79 GB
2026-11-01T13:07:26.2428376Z  FINISHED cal_l40_r4 exit=2 status=aborted
2026-11-01T13:07:26.2428376Z  NOT COMPLETE: cal_l40
2026-11-01T13:08:27.0561796Z  START cal_l15 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.69 GB
2026-11-01T13:08:31.5455217Z  FINISHED cal_l15 exit=2 status=aborted
2026-11-01T13:09:32.3271100Z  START cal_l15_r2 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.84 GB
2026-11-01T13:09:36.7291568Z  FINISHED cal_l15_r2 exit=2 status=aborted
2026-11-01T13:10:37.4276895Z  START cal_l15_r3 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.79 GB
2026-11-01T13:10:41.8113201Z  FINISHED cal_l15_r3 exit=2 status=aborted
2026-11-01T13:11:42.5625415Z  START cal_l15_r4 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.62 GB
2026-11-01T13:11:46.9739991Z  FINISHED cal_l15_r4 exit=2 status=aborted
2026-11-01T13:11:46.9750106Z  NOT COMPLETE: cal_l15
2026-11-01T13:12:47.7723957Z  START cal_uniform design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 2.69 GB
2026-11-01T13:12:52.0242514Z  FINISHED cal_uniform exit=2 status=aborted
2026-11-01T13:13:52.7056590Z  START cal_uniform_r2 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 2.69 GB
2026-11-01T13:13:58.3295053Z  FINISHED cal_uniform_r2 exit=2 status=aborted
2026-11-01T13:14:59.0846096Z  START cal_uniform_r3 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 2.62 GB
2026-11-01T13:15:04.0347929Z  FINISHED cal_uniform_r3 exit=2 status=aborted
2026-11-01T13:17:05.4654757Z  START cal_uniform_r4 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 2.51 GB
2026-11-01T13:17:11.3404330Z  FINISHED cal_uniform_r4 exit=2 status=aborted
2026-11-01T13:17:11.3404330Z  NOT COMPLETE: cal_uniform
2026-11-01T13:19:12.6793707Z  START hold_l120 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 2.85 GB
2026-11-01T13:19:18.1291063Z  FINISHED hold_l120 exit=2 status=aborted
2026-11-01T13:20:18.8686576Z  START hold_l120_r2 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 2.87 GB
2026-11-01T13:20:23.0913484Z  FINISHED hold_l120_r2 exit=2 status=aborted
2026-11-01T13:21:23.9133021Z  START hold_l120_r3 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 2.83 GB
2026-11-01T13:21:28.1979581Z  FINISHED hold_l120_r3 exit=2 status=aborted
2026-11-01T13:22:28.9093176Z  START hold_l120_r4 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 2.9 GB
2026-11-01T13:22:33.2871726Z  FINISHED hold_l120_r4 exit=2 status=aborted
2026-11-01T13:22:33.2944315Z  NOT COMPLETE: hold_l120
2026-11-01T13:23:34.1118462Z  START hold_l40 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 2.71 GB
2026-11-01T13:23:38.5162610Z  FINISHED hold_l40 exit=2 status=aborted
2026-11-01T13:24:39.2589344Z  START hold_l40_r2 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 2.8 GB
2026-11-01T13:24:43.5176845Z  FINISHED hold_l40_r2 exit=2 status=aborted
2026-11-01T13:25:44.2095287Z  START hold_l40_r3 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 2.59 GB
2026-11-01T13:25:48.8526301Z  FINISHED hold_l40_r3 exit=2 status=aborted
2026-11-01T13:37:55.9180517Z  START hold_l40_r4 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 2.43 GB
2026-11-01T13:38:01.7071208Z  FINISHED hold_l40_r4 exit=2 status=aborted
2026-11-01T13:38:01.7188733Z  NOT COMPLETE: hold_l40
2026-11-01T13:38:01.7270466Z  ALLDONE cal_l120,cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40
2026-11-01T13:38:01.9213316Z  STAGE1 STOPPED: calibration session cal_l40 not complete
2026-11-01T13:38:53.4175757Z  STAGE1 STOPPED (exit 1): 20 of 22 attempts after cal_l120_r2 aborted with 'not on mains power (design field require_ac_power)'; the laptop was unplugged (PowerLineStatus Offline, battery 75%) from about 13:03 UTC. RAM was fine (2.4 to 3.5 GB at starts). Completed: cal_l120_r2 (9/9 blocks). Partial/aborted sessions kept as evidence: cal_l120 (7/9, RAM < 0.8 GB before block 7), cal_l40 (2/9, mains lost), and 18 zero-block aborts. Nothing deleted. Fix: scripts/final_run_sessions.ps1 now also waits for mains power before each attempt (design require_ac_power and RAM thresholds unchanged). Needs the charger plugged in.
2026-11-01T15:04:49.0806536Z  START cal_l40 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.62 GB
2026-11-01T15:04:49.9444475Z  FINISHED cal_l40 exit=1 status=aborted
2026-11-01T15:05:50.5474747Z  START cal_l40_r2 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.53 GB
2026-11-01T15:05:51.1624792Z  FINISHED cal_l40_r2 exit=1 status=aborted
2026-11-01T15:06:51.8054452Z  START cal_l40_r3 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.5 GB
2026-11-01T15:06:52.3555056Z  FINISHED cal_l40_r3 exit=1 status=aborted
2026-11-01T15:08:53.5668613Z  START cal_l40_r4 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.72 GB
2026-11-01T15:08:54.1844985Z  FINISHED cal_l40_r4 exit=1 status=aborted
2026-11-01T15:08:54.1874330Z  NOT COMPLETE: cal_l40
2026-11-01T15:09:54.9471350Z  START cal_l15 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.55 GB
2026-11-01T15:09:55.5615597Z  FINISHED cal_l15 exit=1 status=aborted
2026-11-01T15:10:56.3649993Z  START cal_l15_r2 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.37 GB
2026-11-01T15:10:56.9663907Z  FINISHED cal_l15_r2 exit=1 status=aborted
2026-11-01T15:13:18.5239907Z  START cal_l15_r3 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.57 GB
2026-11-01T15:13:19.2162449Z  FINISHED cal_l15_r3 exit=1 status=aborted
2026-11-01T15:14:19.9425890Z  START cal_l15_r4 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 2.57 GB
2026-11-01T15:14:20.5342687Z  FINISHED cal_l15_r4 exit=1 status=aborted
2026-11-01T15:14:20.5377914Z  NOT COMPLETE: cal_l15
2026-11-01T15:15:21.2374700Z  START cal_uniform design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 3.16 GB
2026-11-01T15:15:21.7346178Z  FINISHED cal_uniform exit=1 status=aborted
2026-11-01T15:16:22.3791402Z  START cal_uniform_r2 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 3.18 GB
2026-11-01T15:16:22.9244449Z  FINISHED cal_uniform_r2 exit=1 status=aborted
2026-11-01T15:17:23.5883733Z  START cal_uniform_r3 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 2.6 GB
2026-11-01T15:17:24.2438007Z  FINISHED cal_uniform_r3 exit=1 status=aborted
2026-11-01T15:17:49.7007960Z  NOTE: after mains returned, relaunch (task bhsklfdpw) failed 20+ attempts with exit=1 FileExistsError: retry ids _r2.._r4 already existed from the power-failure attempts. No session started, nothing overwritten. Fixed scripts/final_run_sessions.ps1: each attempt takes the first unused session id. Stage 1 relaunched again.
2026-11-01T15:19:31.1575955Z  START cal_l40_r5 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.51 GB
2026-11-01T15:23:53.2061291Z  FINISHED cal_l40_r5 exit=2 status=aborted
2026-11-01T15:24:53.9504879Z  START cal_l40_r6 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.59 GB
2026-11-01T15:25:08.6374378Z  START cal_uniform_r4 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 1.97 GB
2026-11-01T15:25:09.2969364Z  FINISHED cal_uniform_r4 exit=1 status=aborted
2026-11-01T15:25:09.3004702Z  NOT COMPLETE: cal_uniform
2026-11-01T15:28:34.7886559Z  FINISHED cal_l40_r6 exit=2 status=aborted
2026-11-01T15:29:35.5618173Z  START cal_l40_r7 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 2.47 GB
2026-11-01T15:29:52.1843046Z  START hold_l120 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 1.85 GB
2026-11-01T15:29:52.9090760Z  FINISHED hold_l120 exit=1 status=aborted
2026-11-01T15:32:47.0673388Z  FINISHED cal_l40_r7 exit=2 status=aborted
2026-11-01T15:36:29.1697840Z  START cal_l40_r8 design sha256 C3DD1070B41A390ED38442AD3D107E07ED7093FD194510B26B0FAA3DF1B1FB23 free 5.22 GB
2026-11-01T15:36:36.9608841Z  START hold_l120_r2 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 4.63 GB
2026-11-01T15:36:37.6480685Z  FINISHED hold_l120_r2 exit=1 status=aborted
2026-11-01T15:37:38.2828869Z  START hold_l120_r3 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 3.55 GB
2026-11-01T15:37:38.8558516Z  FINISHED hold_l120_r3 exit=1 status=aborted
2026-11-01T15:38:39.7453157Z  START hold_l120_r4 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 3.3 GB
2026-11-01T15:38:40.7681482Z  FINISHED hold_l120_r4 exit=1 status=aborted
2026-11-01T15:38:40.7681482Z  NOT COMPLETE: hold_l120
2026-11-01T15:39:41.5010742Z  START hold_l40 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 3.1 GB
2026-11-01T15:39:42.2206174Z  FINISHED hold_l40 exit=1 status=aborted
2026-11-01T15:40:43.0036181Z  START hold_l40_r2 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 3.34 GB
2026-11-01T15:40:44.1319147Z  FINISHED hold_l40_r2 exit=1 status=aborted
2026-11-01T15:41:45.0253541Z  START hold_l40_r3 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 3.18 GB
2026-11-01T15:41:45.4917129Z  FINISHED hold_l40_r3 exit=1 status=aborted
2026-11-01T15:41:56.9474674Z  FINISHED cal_l40_r8 exit=0 status=complete
2026-11-01T15:42:46.2847631Z  START hold_l40_r4 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 5.15 GB
2026-11-01T15:42:46.9187719Z  FINISHED hold_l40_r4 exit=1 status=aborted
2026-11-01T15:42:46.9187719Z  NOT COMPLETE: hold_l40
2026-11-01T15:42:46.9187719Z  ALLDONE cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40
2026-11-01T15:42:46.9512951Z  STAGE1 STOPPED: calibration session cal_l15 not complete
2026-11-01T15:42:57.6275491Z  START cal_l15_r5 design sha256 3F4B6820F8C4901D7AD4668C71BBF639C5D4319D30F52B2B1BBF1AAC37E52A8B free 4.86 GB
2026-11-01T15:46:31.0095478Z  FINISHED cal_l15_r5 exit=0 status=complete
2026-11-01T15:47:31.7646215Z  START cal_uniform_r5 design sha256 1C929AD20E3A2013AE9665DF4F4FD2451FB0CD3A6EE2EB3B7878370958E7BB8E free 4.45 GB
2026-11-01T15:49:34.3288516Z  FINISHED cal_uniform_r5 exit=0 status=complete
2026-11-01T15:50:34.9074026Z  START hold_l120_r5 design sha256 5965758E612BF443257E10F2FB1D4BF255F72F779AA742C3B784AA4B1E79DB5A free 4.82 GB
2026-11-01T15:55:44.5435736Z  FINISHED hold_l120_r5 exit=0 status=complete
2026-11-01T15:56:45.1348564Z  START hold_l40_r5 design sha256 41354BE2BD35CBE8BA97D9EB282FD944D93CD465312EBFBC6A56ABBAD661C159 free 3.96 GB
2026-11-01T15:59:50.3692339Z  FINISHED hold_l40_r5 exit=0 status=complete
2026-11-01T15:59:50.3692339Z  ALLDONE cal_l40,cal_l15,cal_uniform,hold_l120,hold_l40
2026-11-01T15:59:50.4162179Z  calibration sessions complete: D:\cao project\data\results\final_20261101\calibration\sessions\cal_l15_r5; D:\cao project\data\results\final_20261101\calibration\sessions\hold_l40_r5; D:\cao project\data\results\final_20261101\calibration\sessions\cal_l120_r2; D:\cao project\data\results\final_20261101\calibration\sessions\cal_uniform_r5; D:\cao project\data\results\final_20261101\calibration\sessions\hold_l120_r5; D:\cao project\data\results\final_20261101\calibration\sessions\cal_l40_r8
2026-11-01T15:59:52.2627121Z  model D5C54C2C25A9C0748E9A04ADF36052FDA46752BB5B34AABCB198423657A78661 terms D7AA01B7D24D1C43FC2EBBCADA8EC41BAF34301C2F673E1ED3F4A992324185B4
2026-11-01T15:59:58.8579880Z  evaluation designs written; hashes in eval\designs_sha256.txt; protocol sha256 A51F8B1F508A13F64F5189F9DDAA760763E727F7838490A5572A3CEDEFDF974B
2026-11-01T16:00:59.3961066Z  START smoke design sha256 171D2FB3AF452A08FA74B79B831D5F7B62820458EBEFC9E13E71EE36C6FD9499 free 4.36 GB
2026-11-01T16:09:27.7890611Z  FINISHED smoke exit=0 status=complete
2026-11-01T16:09:27.7890611Z  ALLDONE smoke
2026-11-01T16:09:28.8386309Z  smoke session D:\cao project\data\results\final_20261101\eval\sessions\smoke : runs not ok/verified: 0 []
2026-11-01T16:09:28.8386309Z  STAGE1 COMPLETE
2026-11-01T16:10:39.0899016Z  Stage 1 COMPLETE (STAGE1_DONE.txt). Smoke session eval\sessions\smoke: 2 blocks, 48 runs, 0 not ok/verified; analysed to eval\analysis_smoke (sanity check only, not a result). During the smoke analysis a Python 3.11 SyntaxError (nested f-string) in scripts\final_analyze.py line 191 was fixed before any output was written; all scripts\final_*.py now compile. Hold-out accuracy (median APE): E 4-9%, P 8-11%, G 23-31% (see models\train.stdout.txt).
2026-11-01T16:10:39.0899016Z  PROTOCOL FROZEN before the first evaluation session: docs\final\PROTOCOL_final.md sha256 A51F8B1F508A13F64F5189F9DDAA760763E727F7838490A5572A3CEDEFDF974B; eval\designs_sha256.txt sha256 60D3DF70EA59FE0ABB0AF39995E6F2311703996E0F5AECDE65FC18B22DCC5D73; models param_model_final.json D5C54C2C25A9C0748E9A04ADF36052FDA46752BB5B34AABCB198423657A78661, e2e_terms_final.json D7AA01B7D24D1C43FC2EBBCADA8EC41BAF34301C2F673E1ED3F4A992324185B4. Stage 2 (scripts\final_stage2.ps1) starts the six evaluation sessions in order eval_h16_l120, eval_uniform, eval_h04_l120, eval_h40_l120, eval_h16_l40, eval_h16_l15.
2026-11-01T16:11:44.2157650Z  START eval_h16_l120 design sha256 73F25274906EEF5A123AF4A7B4C495785849D56808CB49E1D6EAC88B77FC9566 free 4.46 GB
2026-11-01T17:23:21.8228306Z  FINISHED eval_h16_l120 exit=0 status=complete
2026-11-01T17:23:21.8228306Z  ALLDONE eval_h16_l120
2026-11-01T17:23:22.1929308Z  analysed eval_h16_l120 -> data\results\final_20261101\eval\analysis_h16_l120 (exit 2) session eval_h16_l120
2026-11-01T17:23:49.1645080Z  eval_h16_l120 (primary) COMPLETE. Its automatic analysis failed (exit 2): scripts\final_stage2.ps1 splatted the string '--confirmatory' per character (script bug, no data involved; analysis_h16_l120 was not created). Script fixed (@(if ...)). The analysis will be run by hand after all evaluation sessions finish, so it does not compete for CPU with timed runs. eval_uniform is now running (running stage-2 instance keeps the old script text; only the h16_l120 analysis is affected).
2026-11-01T17:24:22.7938164Z  START eval_uniform design sha256 36B8F02AD08691E5A8030E8C6463D6201236A2BC66FC84C5A411C925C97A8CE3 free 4.8 GB
2026-11-01T17:41:43.7111663Z  FINISHED eval_uniform exit=0 status=complete
2026-11-01T17:41:43.7111663Z  ALLDONE eval_uniform
2026-11-01T17:41:51.1258717Z  analysed eval_uniform -> data\results\final_20261101\eval\analysis_uniform (exit 0) session eval_uniform
2026-11-01T17:42:51.7888829Z  START eval_h04_l120 design sha256 07E2FD328D56198C958A81A7721C98EAA16420AA60BEEEA57D53123897860C0E free 4.33 GB
2026-11-01T18:11:53.2536422Z  FINISHED eval_h04_l120 exit=0 status=complete
2026-11-01T18:11:53.2556481Z  ALLDONE eval_h04_l120
2026-11-01T18:12:02.8308502Z  analysed eval_h04_l120 -> data\results\final_20261101\eval\analysis_h04_l120 (exit 0) session eval_h04_l120
2026-11-01T18:13:03.4718726Z  START eval_h40_l120 design sha256 DCC84364B9E6D74EF232F501B059D96C8536B9245B40FB83E606EFF404808E11 free 4.02 GB
2026-11-01T19:36:04.1567601Z  FINISHED eval_h40_l120 exit=0 status=complete
2026-11-01T19:36:04.1567601Z  ALLDONE eval_h40_l120
2026-11-01T19:36:12.7075987Z  analysed eval_h40_l120 -> data\results\final_20261101\eval\analysis_h40_l120 (exit 0) session eval_h40_l120
2026-11-01T19:37:13.2419211Z  START eval_h16_l40 design sha256 C5F6306C44941A69A7C9DD9BFEA703B2F4BAF4F93294E78CA5010F726C725571 free 4.37 GB
2026-11-01T20:03:31.3839824Z  FINISHED eval_h16_l40 exit=0 status=complete
2026-11-01T20:03:31.3839824Z  ALLDONE eval_h16_l40
2026-11-01T20:03:41.0235254Z  analysed eval_h16_l40 -> data\results\final_20261101\eval\analysis_h16_l40 (exit 0) session eval_h16_l40
2026-11-01T20:04:41.5757147Z  START eval_h16_l15 design sha256 26F6E69AB9E019700CFF6A865696DAC003A474BA9C3132FA3A412E2AAE5E4226 free 4.12 GB
2026-11-01T20:27:08.5457891Z  FINISHED eval_h16_l15 exit=0 status=complete
2026-11-01T20:27:08.5457891Z  ALLDONE eval_h16_l15
2026-11-01T20:27:17.3531919Z  analysed eval_h16_l15 -> data\results\final_20261101\eval\analysis_h16_l15 (exit 0) session eval_h16_l15
2026-11-01T20:27:17.3531919Z  STAGE2 COMPLETE: all six evaluation sessions complete and analysed
2026-11-01T20:27:44.2647415Z  STAGE2 COMPLETE. All six evaluation sessions complete; analysis_h16_l120 (--confirmatory) run by hand after stage 2 (exit 0; 576 of 600 runs included).
2026-11-01T20:38:42.4078592Z  Phase F: workload_features.csv written (pre-execution features from the frozen param model). NOTE (disclosure): the primary session summary and confirmatory table (h16_l120) had already been read when the features were computed; features use only the DAG and the model, never a result, but the order stated in protocol section 10 (features before reading results) was not kept for the primary workload.
2026-11-01T21:00:42.9087726Z  Phase F DECISION: hybrid NOT justified. eval\hybrid_check.md (sha256 8747ED0DD635B59782A0D9034FA51984D7DFB2688EA4047B46573F1964494E81): 17 workload x config cells, oracle best-of-B4-and-PRED headroom over PRED_RANK_GREEDY max 1.1%, mean 0.08%, 0 cells above the +-2% margin. PRED_RANK_GREEDY is never meaningfully worse than B4; where it ties B4 (uniform, h16_l15) there is nothing for a selector to gain. No hybrid built; no held-out hybrid sessions run. Note: RESULTS_TABLE_FINAL.csv first written with 2-block smoke rows by mistake; renamed to eval\RESULTS_TABLE_FINAL_with_smoke_rows_superseded.csv (kept), script fixed to skip analysis_smoke, table regenerated (146 rows). Same for cross_workload.md.
2026-11-02T00:51:08.2088987Z  DELIVERABLES COMPLETE: CAO_FINAL_EXPERIMENT_REPORT.md (generated from analysis files), RESULTS_TABLE_FINAL.csv (146 rows), RESEARCH_CLAIMS_AND_LIMITATIONS.md section E, PROJECT_MASTER_DOCUMENTATION.md section 33, PROJECT_BACKBONE.md part 12, FACULTY_DEMO_CHECKLIST/SCRIPT, EVIDENCE_INDEX, publications/09_Final_Static_vs_Dynamic_Demo.pptx+pdf, publications/README_SUBMISSION_INDEX.md addendum, release bundle cao_release_bundle_final_20261102.zip (5313 files, 124.6 MB, testzip OK). Full test suite: 521 passed (preservation/pytest_final.stdout.txt). Originals of edited documents backed up in backups/docs.
