import { useState, useRef, useEffect } from 'react';
import api from '../services/api';

export default function DataChat({ company, product, snapshot, asOfDate, currency }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const question = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      const response = await api.post(
        `/companies/${company}/products/${product}/chat`,
        {
          question,
          history: messages.slice(-6)
        },
        { params: { snapshot, as_of_date: asOfDate, currency } }
      );

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.answer
      }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      }]);
    }
    setLoading(false);
  };

  const suggestions = [
    "What's driving the recent increase in denial rates?",
    "Which month had the highest deployment?",
    "Show me the worst performing cohorts",
    "What is the pending exposure breakdown?",
  ];

  return (
    <div className="rounded-xl overflow-hidden"
         style={{ backgroundColor: '#111D3E', border: '1px solid #1B2B5A' }}>
      <div className="p-6 pb-4" style={{ borderBottom: '1px solid #1B2B5A' }}>
        <h3 className="text-sm font-semibold text-white">Ask Questions About This Portfolio</h3>
        <p className="text-xs mt-1" style={{ color: '#64748B' }}>
          Ask anything about the data — trends, specific deals, performance drivers
        </p>
      </div>

      {/* Messages */}
      <div className="p-4 space-y-4 overflow-y-auto"
           style={{ minHeight: '200px', maxHeight: '400px' }}>

        {messages.length === 0 && (
          <div className="space-y-2">
            <div className="text-xs mb-3" style={{ color: '#64748B' }}>
              Suggested questions:
            </div>
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => setInput(s)}
                className="block w-full text-left text-xs px-3 py-2 rounded-lg transition-colors"
                style={{
                  backgroundColor: '#0A0F1E',
                  border: '1px solid #1B2B5A',
                  color: '#93C5FD'
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = '#3B82F6'}
                onMouseLeave={e => e.currentTarget.style.borderColor = '#1B2B5A'}>
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className="max-w-[85%] rounded-xl px-4 py-3 text-sm"
              style={{
                backgroundColor: msg.role === 'user' ? '#3B82F6' : '#0A0F1E',
                color: 'white',
                border: msg.role === 'assistant' ? '1px solid #1B2B5A' : 'none'
              }}>
              {msg.content.split('\n').map((line, j) => (
                <p key={j} className={j > 0 ? 'mt-1' : ''}>{line}</p>
              ))}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl px-4 py-3 flex items-center gap-2"
                 style={{ backgroundColor: '#0A0F1E', border: '1px solid #1B2B5A' }}>
              <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent
                              rounded-full animate-spin" />
              <span className="text-xs" style={{ color: '#64748B' }}>Analyzing...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4" style={{ borderTop: '1px solid #1B2B5A' }}>
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage()}
            placeholder="Ask a question about this portfolio..."
            className="flex-1 text-sm px-4 py-2.5 rounded-lg outline-none"
            style={{
              backgroundColor: '#0A0F1E',
              border: '1px solid #1B2B5A',
              color: 'white',
            }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              backgroundColor: loading || !input.trim() ? '#1B2B5A' : '#3B82F6',
              color: 'white',
              opacity: loading || !input.trim() ? 0.5 : 1
            }}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}