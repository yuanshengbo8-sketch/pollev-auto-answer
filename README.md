# Poll Everywhere 自动答题助手

> A local Playwright bot for pollev.com: open it before class, it sets your screen name, keeps the screen awake, and answers every multiple-choice poll with a random option. Works on Windows and macOS.

上课前打开它，它会自动进入老师的 Poll Everywhere 页面、填好你的名字，然后一直盯着页面；一旦出现选择题，随机选一个并提交。每出现一道新题，任务栏上的浏览器图标会闪烁提醒你（填空题程序不会答，看到闪烁就自己去答）。运行期间电脑不会息屏、不会休眠。Windows 和 Mac 都能用。

## 一、安装（只做一次）

1. 安装 Python 3.10 或更高：https://www.python.org/downloads/
   - Windows 安装时务必勾选 **"Add python.exe to PATH"**
   - Mac 一般自带 python3，也可以用上面的安装包
2. 下载本仓库（Code → Download ZIP，解压到任意位置），然后：
   - **Windows**：双击 `install.bat`
   - **Mac**：打开"终端"，把 `install.sh` 拖进去，回车（或运行 `bash install.sh`）
   - 第一次会下载一个 Chromium 浏览器（约 150MB）

## 二、使用

- **Windows**：双击 `run.bat`
- **Mac**：双击 `run.command`（第一次若提示无法打开，右键 → 打开；或在终端运行 `bash run.command`）

第一次运行会问你两个问题：

1. **Poll Everywhere 网址**：填完整网址（如 `https://pollev.com/jiancai`）或者直接填老师的用户名（如 `jiancai`）
2. **你的名字**：就是在 Poll Everywhere 上显示的 screen name

两项都保存在 `config.json` 里，以后启动不再问。换老师、换名字时直接编辑这个文件即可。

之后程序会打开浏览器、填名字、开始监测，一直到你关掉窗口（或按 Ctrl+C）为止。**上课期间别关这个窗口。**

## 三、修改设置（config.json）

| 字段 | 含义 | 默认 |
|---|---|---|
| `url` | 投票页面地址或老师用户名 | 第一次运行时输入 |
| `screen_name` | 你的名字 | 第一次运行时输入 |
| `poll_interval_seconds` | 多久检查一次页面（秒） | `1.0` |
| `reload_if_idle_minutes` | 空闲多久刷新一次页面保活 | `10` |
| `headless` | `true` 则不显示浏览器窗口 | `false` |
| `open_ended_text` | 填空题自动填的内容；留空则跳过填空题 | 空 |

命令行参数（可选）：

```bash
python pollev_bot.py --minutes 90          # 监测 90 分钟后自动退出
python pollev_bot.py --url jiancai         # 临时换一个老师，不改 config.json
python pollev_bot.py --name "张三"          # 临时换名字
```

## 四、它是怎么工作的

- 用 Playwright 驱动一个真实的 Chromium 浏览器打开页面，和你手动操作完全一样。
- 浏览器资料保存在 `browser-profile/` 里，所以名字、Cookie 下次还在。
- 每 1 秒检查一次页面：找到选择题的选项（单选框 / 复选框 / 按钮式选项）就随机点一个，再点 Submit；没有单独提交按钮的就点选即提交。
- 提交后会确认页面确实变成"已提交"状态，否则会重试（最多 6 次，中间会刷新页面）。
- **新题提醒**：每出现一道新题（包括程序不答的填空题），Windows 上浏览器和程序窗口会在任务栏闪烁，直到你点开为止；Mac 上弹出一条系统通知。不会发出声音。
- 实时连接断开超过 30 秒、或页面空闲超过 10 分钟，会自动刷新页面，避免错过题目。
- **防息屏**：Windows 用系统 API 声明"显示器和系统需要保持开启"并每分钟续期；Mac 启动 `caffeinate -dims`。程序退出时自动恢复原设置。学校/公司强制锁屏策略无法绕过。
- 每次提交后截图保存到 `logs/`，所有动作记录在 `logs/pollev.log`，方便事后核对。

## 五、常见问题

- **双击没反应 / 一闪而过**：多半是 Python 没装或没加进 PATH。在终端里运行 `python --version` 看看。
- **填错了网址或名字**：打开 `config.json` 改掉对应字段，或者把这个文件删了，下次启动重新问。
- **想停止**：关掉那个黑色窗口，或按 Ctrl+C。
- **本地自测**：`python pollev_bot.py --minutes 1.5 --url "file:///完整路径/test/mock_poll.html" --name test` 会用一个模拟页跑一遍所有题型（单选、按钮、多选、点击时题目刷新、填空）。

## 开源协议

MIT
