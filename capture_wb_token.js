/**
 * WorkBuddy 明文 token 捕获工具（纯 Node.js 内置模块，无需依赖）
 * 通过 Chrome DevTools Protocol 监听 WorkBuddy 的网络请求，
 * 从 Authorization header 中提取明文 accessToken。
 *
 * 使用方法：
 * 1. 关闭 WorkBuddy
 * 2. 命令行启动："D:\1\ai\workbuddy\WorkBuddy.exe" --remote-debugging-port=9222
 * 3. 运行本脚本：node capture_wb_token.js
 */

const http = require('http');
const crypto = require('crypto');
const fs = require('fs');

const DEBUG_PORT = 9222;
const OUTPUT_FILE = __dirname + '\\token.info';

// ===== 简单的 WebSocket 客户端（纯 Node.js 内置实现）=====
class SimpleWebSocket {
  constructor(url) {
    this.url = new URL(url);
    this.callbacks = {};
    this.sendQueue = [];
    this.connected = false;
    this._connect();
  }

  on(event, cb) {
    this.callbacks[event] = cb;
  }

  _connect() {
    const key = crypto.randomBytes(16).toString('base64');
    const options = {
      hostname: this.url.hostname,
      port: this.url.port,
      path: this.url.pathname + this.url.search,
      method: 'GET',
      headers: {
        'Upgrade': 'websocket',
        'Connection': 'Upgrade',
        'Sec-WebSocket-Key': key,
        'Sec-WebSocket-Version': '13'
      }
    };

    const req = http.request(options);
    req.on('upgrade', (res, socket, head) => {
      this.socket = socket;
      this.connected = true;
      this._buffer = head || Buffer.alloc(0);
      this._frameBuf = [];

      socket.on('data', (chunk) => this._onData(chunk));
      socket.on('close', () => this.callbacks.close?.());
      socket.on('error', (e) => this.callbacks.error?.(e));

      // 发送排队的消息
      while (this.sendQueue.length > 0) {
        this._sendFrame(this.sendQueue.shift());
      }

      this.callbacks.open?.();
    });
    req.on('error', (e) => this.callbacks.error?.(e));
    req.end();
  }

  send(data) {
    const frame = this._buildFrame(data);
    if (this.connected) {
      this._sendFrame(frame);
    } else {
      this.sendQueue.push(frame);
    }
  }

  _sendFrame(frame) {
    this.socket.write(frame);
  }

  _buildFrame(data) {
    const payload = Buffer.from(data, 'utf8');
    const len = payload.length;
    let header;

    if (len < 126) {
      header = Buffer.alloc(6);
      header[0] = 0x81; // text + fin
      header[1] = 0x80 | len; // masked
      const mask = crypto.randomBytes(4);
      mask.copy(header, 2);
      for (let i = 0; i < len; i++) {
        payload[i] ^= mask[i % 4];
      }
      return Buffer.concat([header, payload]);
    } else if (len < 65536) {
      header = Buffer.alloc(8);
      header[0] = 0x81;
      header[1] = 0x80 | 126;
      header.writeUInt16BE(len, 2);
      const mask = crypto.randomBytes(4);
      mask.copy(header, 4);
      for (let i = 0; i < len; i++) {
        payload[i] ^= mask[i % 4];
      }
      return Buffer.concat([header, payload]);
    } else {
      header = Buffer.alloc(14);
      header[0] = 0x81;
      header[1] = 0x80 | 127;
      header.writeBigUInt64BE(BigInt(len), 2);
      const mask = crypto.randomBytes(4);
      mask.copy(header, 10);
      for (let i = 0; i < len; i++) {
        payload[i] ^= mask[i % 4];
      }
      return Buffer.concat([header, payload]);
    }
  }

  _onData(chunk) {
    this._buffer = Buffer.concat([this._buffer, chunk]);
    this._parseFrames();
  }

  _parseFrames() {
    while (this._buffer.length >= 2) {
      const b0 = this._buffer[0];
      const b1 = this._buffer[1];
      const fin = (b0 & 0x80) !== 0;
      const opcode = b0 & 0x0f;
      const masked = (b1 & 0x80) !== 0;
      let payloadLen = b1 & 0x7f;
      let offset = 2;

      if (payloadLen === 126) {
        if (this._buffer.length < 4) return;
        payloadLen = this._buffer.readUInt16BE(2);
        offset = 4;
      } else if (payloadLen === 127) {
        if (this._buffer.length < 10) return;
        payloadLen = Number(this._buffer.readBigUInt64BE(2));
        offset = 10;
      }

      let maskKey = null;
      if (masked) {
        if (this._buffer.length < offset + 4) return;
        maskKey = this._buffer.slice(offset, offset + 4);
        offset += 4;
      }

      if (this._buffer.length < offset + payloadLen) return;

      let payload = this._buffer.slice(offset, offset + payloadLen);
      if (masked && maskKey) {
        payload = Buffer.from(payload);
        for (let i = 0; i < payload.length; i++) {
          payload[i] ^= maskKey[i % 4];
        }
      }

      this._buffer = this._buffer.slice(offset + payloadLen);

      if (opcode === 0x1) {
        // text frame
        this._frameBuf.push(payload);
        if (fin) {
          const data = Buffer.concat(this._frameBuf).toString('utf8');
          this._frameBuf = [];
          this.callbacks.message?.(data);
        }
      } else if (opcode === 0x8) {
        // close
        this.socket.end();
      } else if (opcode === 0x9) {
        // ping -> pong
        const pong = Buffer.alloc(2 + payload.length);
        pong[0] = 0x8a;
        pong[1] = payload.length;
        payload.copy(pong, 2);
        this.socket.write(pong);
      }
    }
  }

  close() {
    if (this.socket) {
      this.socket.end();
    }
  }
}

// ===== 主逻辑 =====
function getTargets() {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${DEBUG_PORT}/json`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function main() {
  console.log('='.repeat(60));
  console.log('  WorkBuddy 明文 Token 捕获工具');
  console.log('='.repeat(60));
  console.log();
  console.log('正在连接 WorkBuddy 调试端口 ' + DEBUG_PORT + '...');
  console.log();

  let targets;
  try {
    targets = await getTargets();
  } catch (e) {
    console.error('❌ 连接失败！');
    console.error();
    console.error('请按以下步骤操作：');
    console.error();
    console.error('1. 完全关闭 WorkBuddy（包括托盘图标）');
    console.error('2. 按 Win+R，输入以下命令并回车：');
    console.error('   "D:\\1\\ai\\workbuddy\\WorkBuddy.exe" --remote-debugging-port=9222');
    console.error('3. 等待 WorkBuddy 完全启动并登录');
    console.error('4. 重新运行本脚本');
    console.error();
    console.error('错误详情:', e.message);
    process.exit(1);
  }

  console.log(`找到 ${targets.length} 个调试目标`);

  // 优先选 page 类型的目标
  const pageTarget = targets.find(t => t.type === 'page') || targets[0];
  if (!pageTarget || !pageTarget.webSocketDebuggerUrl) {
    console.error('找不到可用的调试目标');
    process.exit(1);
  }

  console.log(`目标页面: ${pageTarget.title || pageTarget.url}`);
  console.log();
  console.log('🔍 正在监听网络请求...');
  console.log('💡 请在 WorkBuddy 中进行一些操作（切换页面、点击签到等）');
  console.log('   脚本会自动捕获带 Authorization 的请求');
  console.log();

  const ws = new SimpleWebSocket(pageTarget.webSocketDebuggerUrl);
  let reqId = 0;
  let found = false;

  ws.on('open', () => {
    // 启用 Network 域
    ws.send(JSON.stringify({ id: ++reqId, method: 'Network.enable' }));
  });

  ws.on('message', (data) => {
    if (found) return;
    const msg = JSON.parse(data);

    if (msg.method === 'Network.requestWillBeSent') {
      const headers = msg.params.request.headers;
      const auth = headers['Authorization'] || headers['authorization'];
      if (auth && auth.startsWith('Bearer ')) {
        const token = auth.substring(7);
        const userId = headers['X-User-Id'] || headers['x-user-id'] || '';
        const domain = headers['X-Domain'] || headers['x-domain'] || 'copilot.tencent.com';

        found = true;
        console.log('✅ 成功捕获到明文 token！');
        console.log();
        console.log('  Token 长度:', token.length, '字符');
        console.log('  User ID:', userId || '(未获取到)');
        console.log('  Domain:', domain);

        // 检查 token 是否是 JWT
        try {
          const parts = token.split('.');
          if (parts.length === 3) {
            const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
            if (payload.exp) {
              const expDate = new Date(payload.exp * 1000);
              console.log('  Token 过期时间:', expDate.toLocaleString('zh-CN'));
            }
          }
        } catch (e) {
          // 不是 JWT 格式也没关系
        }

        // 保存为 token.info（明文格式）
        const tokenInfo = {
          account: { uid: userId },
          auth: {
            accessToken: token,
            domain: domain,
            tokenType: 'Bearer'
          }
        };

        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(tokenInfo, null, 2), 'utf8');
        console.log();
        console.log('💾 已保存到:', OUTPUT_FILE);
        console.log();
        console.log('🎉 完成！现在重启签到服务即可正常使用 WorkBuddy 签到。');
        console.log('   提示：token.info 已被 .gitignore 忽略，不会提交到仓库。');

        ws.close();
        process.exit(0);
      }
    }
  });

  ws.on('error', (e) => {
    console.error('WebSocket 错误:', e.message);
    process.exit(1);
  });

  // 60 秒超时
  setTimeout(() => {
    if (!found) {
      console.log();
      console.log('⏰ 60 秒内未捕获到带 Authorization 的请求。');
      console.log();
      console.log('请尝试：');
      console.log('  1. 在 WorkBuddy 中点击「积分」或「签到」相关功能');
      console.log('  2. 切换不同的页面（如「发现」「工作台」等）');
      console.log('  3. 确认 WorkBuddy 已登录且网络正常');
      console.log();
      console.log('如果还是不行，可以尝试手动获取 token：');
      console.log('  1. 打开浏览器，按 F12 打开开发者工具');
      console.log('  2. 访问 WorkBuddy 网页版并登录');
      console.log('  3. 在 Network 面板中找到 API 请求，复制 Authorization header');
      ws.close();
      process.exit(1);
    }
  }, 60000);
}

main();
