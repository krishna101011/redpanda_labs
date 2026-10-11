import { useCallback, useEffect, useRef, useState } from 'react';
import { Terminal as XTerm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { Circle, Maximize2, RotateCcw, TerminalSquare } from 'lucide-react';
import '@xterm/xterm/css/xterm.css';

type Props = { challengeId: string; onStatus?: (status: 'connecting' | 'connected' | 'error') => void; onSelectionChange?: (text: string) => void; };

export function TerminalPanel({ challengeId, onStatus, onSelectionChange }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const terminal = useRef<XTerm | null>(null);
  const socket = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<'connecting' | 'connected' | 'error'>('connecting');
  const [fullscreen, setFullscreen] = useState(false);

  const send = useCallback((event: Record<string, unknown>) => {
    if (socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify(event));
  }, []);

  useEffect(() => {
    if (!host.current) return;
    const term = new XTerm({ cursorBlink: true, convertEol: false, fontFamily: '"JetBrains Mono", "Cascadia Code", monospace', fontSize: 13, lineHeight: 1.45, scrollback: 3000,
      theme: { background: '#0b0d0e', foreground: '#d6dbd9', cursor: '#f26b68', selectionBackground: '#76363488', black: '#17191a', red: '#f26b68', green: '#97c9a4', yellow: '#e6c98d', blue: '#95b9ee', magenta: '#c7a4e8', cyan: '#8ecac7', white: '#d6dbd9', brightBlack: '#646b6b' } });
    const fit = new FitAddon(); term.loadAddon(fit); term.open(host.current); terminal.current = term;
    const resize = () => { try { fit.fit(); send({ type: 'resize', rows: term.rows, cols: term.cols }); } catch { /* The panel may be hidden while collapsed. */ } };
    const timer = window.setTimeout(resize, 60);
    const socketUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/terminal/${challengeId}`;
    const ws = new WebSocket(socketUrl); socket.current = ws;
    ws.onopen = () => { setStatus('connecting'); onStatus?.('connecting'); };
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { type: string; data?: string; message?: string };
        if (message.type === 'output' && message.data) term.write(message.data);
        else if (message.type === 'ready') { setStatus('connected'); onStatus?.('connected'); term.focus(); }
        else if (message.type === 'error') { setStatus('error'); onStatus?.('error'); term.writeln(`\r\n\x1b[31m${message.message ?? 'Terminal error'}\x1b[0m`); }
      } catch { term.write(String(event.data)); }
    };
    ws.onerror = () => { setStatus('error'); onStatus?.('error'); };
    ws.onclose = (event) => { if (event.code !== 1000 && event.code !== 1001) { setStatus('error'); onStatus?.('error'); } };
    const dataDisposable = term.onData((data) => send({ type: 'input', data }));
    const resizeDisposable = term.onResize((size) => send({ type: 'resize', rows: size.rows, cols: size.cols }));
    const selectionDisposable = term.onSelectionChange(() => onSelectionChange?.(term.getSelection()));
    const observer = new ResizeObserver(resize); observer.observe(host.current);
    return () => {
      window.clearTimeout(timer); observer.disconnect(); dataDisposable.dispose(); resizeDisposable.dispose(); selectionDisposable.dispose(); ws.close();
      terminal.current = null; socket.current = null; term.dispose();
    };
  }, [challengeId, onStatus, onSelectionChange, send]);

  const clear = () => terminal.current?.clear();
  const focus = () => terminal.current?.focus();
  return <section className={`terminal-panel ${fullscreen ? 'terminal-panel--full' : ''}`}>
    <div className="terminal-topbar">
      <div className="terminal-title"><TerminalSquare size={15}/><span>LAB TERMINAL</span><span className={`terminal-state terminal-state--${status}`}><Circle size={7} fill="currentColor"/>{status === 'connected' ? 'Connected' : status === 'connecting' ? 'Connecting' : 'Disconnected'}</span></div>
      <div className="icon-actions"><button className="icon-button" title="Clear visible terminal" onClick={clear}><RotateCcw size={14}/></button><button className="icon-button" title="Focus terminal" onClick={focus}><Maximize2 size={14}/></button><button className="icon-button" title="Toggle terminal expand" onClick={() => setFullscreen((value) => !value)}><Maximize2 size={14}/></button></div>
    </div>
    <div className="terminal-host" ref={host} onClick={focus} aria-label="Interactive Bash terminal" />
    <div className="terminal-bottom"><span>bash · isolated Docker workspace</span><span><kbd>Ctrl</kbd> + <kbd>C</kbd> interrupt</span></div>
  </section>;
}
