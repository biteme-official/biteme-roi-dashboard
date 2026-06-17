const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

// Load .env.local
const envPath = path.join(__dirname, '.env.local');
if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, 'utf8').split('\n').forEach(line => {
    const m = line.match(/^([^#=]+)=(.*)$/);
    if (!m) return;
    const key = m[1].trim();
    const val = m[2].trim().replace(/^["']|["']$/g, '');
    process.env[key] = val;
  });
}

const handler = require('./api/tableau-data');
const PORT = 3001;

function wrapRes(res) {
  res.status = (code) => {
    res.statusCode = code;
    return {
      end: () => res.end(),
      json: (obj) => {
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify(obj));
      }
    };
  };
  res.json = (obj) => {
    res.setHeader('Content-Type', 'application/json');
    res.end(JSON.stringify(obj));
  };
  return res;
}

const server = http.createServer(async (req, res) => {
  const parsed = url.parse(req.url, true);

  if (parsed.pathname === '/api/tableau-data') {
    req.query = parsed.query;
    return handler(req, wrapRes(res));
  }

  if (parsed.pathname === '/' || parsed.pathname === '/index.html') {
    const filePath = path.join(__dirname, 'index.html');
    fs.readFile(filePath, (err, data) => {
      if (err) { res.writeHead(404); return res.end('Not found'); }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(data);
    });
    return;
  }

  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`Dashboard running at http://localhost:${PORT}`);
});
