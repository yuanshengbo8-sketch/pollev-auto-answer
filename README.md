# Poll Everywhere 自动答题助手

> A local Playwright bot that opens a pollev.com page at a scheduled time, sets your screen name, and answers every multiple-choice poll with a random option. Works on Windows and macOS.

每周三 18:00 自动打开 `https://pollev.com/jiancai`，填好你的名字，盯着页面；一旦出现选择题，随机选一个并提交。Windows 和 Mac 都能用。

`config.json` 不会上传到 GitHub（里面有你的名字）；第一次运行会按 `config.example.json` 的默认值自动生成。

## 一、安装（只做一次）

1. 安装 Python 3.10 或更高：https://www.python.org/downloads/
   - Windows 安装时务必勾选 **"Add python.exe to PATH"**
   - Mac 一般自带 python3，也可以用上面的安装包
2. 把这个文件夹放到任意位置，然后：
   - **Windows**：双击 `install.bat`
   - **Mac**：打开"终端"，把 `install.sh` 拖进去，回车（或运行 `bash install.sh`）
   - 第一次会下载一个 Chromium 浏览器（约 150MB）

## 二、使用

- **Windows**：双击 `run.bat`
- **Mac**：双击 `run.command`（第一次若提示无法打开，右键 → 打开；或在终端运行 `bash run.command`）

第一次运行会让你输入名字（就是在 Poll Everywhere 上显示的 screen name），之后保存在 `config.json` 里。

程序启动后会显示"下一次自动开始：xxxx-xx-xx 17:55"，然后一直等着。到点自动打开浏览器、填名字、开始监测 3 小时，结束后继续等下一个周三。**窗口别关、电脑别关机**（程序运行期间会自动阻止电脑休眠）。

想马上试一下效果：双击 `test_now.bat`（Mac：`test_now.command`），会立刻开始监测 10 分钟。

## 三、修改设置（config.json）

| 字段 | 含义 | 默认 |
|---|---|---|
| `url` | 投票页面地址 | `https://pollev.com/jiancai` |
| `screen_name` | 你的名字 | 第一次运行时输入 |
| `weekday` | 星期几（`wednesday` / `周三`） | `wednesday` |
| `start_time` | 开始时间（24 小时制） | `18:00` |
| `start_early_minutes` | 提前几分钟打开页面 | `5` |
| `duration_hours` | 监测多久（小时） | `3` |
| `poll_interval_seconds` | 多久检查一次页面（秒） | `1.0` |
| `reload_if_idle_minutes` | 空闲多久刷新一次页面保活 | `10` |
| `headless` | `true` 则不显示浏览器窗口 | `false` |
| `open_ended_text` | 填空题自动填的内容；留空则跳过填空题 | 空 |

## 四、它是怎么工作的

- 用 Playwright 驱动一个真实的 Chromium 浏览器打开页面，和你手动操作完全一样。
- 浏览器资料保存在 `browser-profile/` 里，所以名字、Cookie 下次还在。
- 每 1 秒检查一次页面：找到选择题的选项（单选框 / 复选框 / 按钮式选项）就随机点一个，再点 Submit；没有单独提交按钮的就点选即提交。
- 提交后会确认页面确实变成"已提交"状态，否则会重试（最多 6 次，中间会刷新页面）。
- 实时连接断开超过 30 秒、或页面空闲超过 10 分钟，会自动刷新页面，避免错过题目。
- 每次提交后截图保存到 `logs/`，所有动作记录在 `logs/pollev.log`，方便事后核对。

## 五、常见问题

- **双击没反应 / 一闪而过**：多半是 Python 没装或没加进 PATH。在终端里运行 `python --version` 看看。
- **想换名字**：改 `config.json` 里的 `screen_name`，下次启动会自动改成新名字。
- **想停止**：关掉那个黑色窗口，或按 Ctrl+C。
- **本地自测**：`python pollev_bot.py --now --minutes 1 --url "file:///完整路径/test/mock_poll.html"` 会用一个模拟页跑一遍三种题型。
