import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Loader2,
  MessageSquare,
  Plus,
  Send,
  Square,
  Trash2,
  Wrench,
} from 'lucide-react'
import { useChat, type ChatMessage, type ToolCall } from '../hooks/useChat'

const SUGGESTED_QUESTIONS = [
  'What were my highest transactions last month?',
  'Show my spending breakdown by category',
  'Which card do I spend the most on?',
  'How does this month compare to last month?',
]

export function Chat() {
  const {
    chats,
    currentChatId,
    messages,
    isStreaming,
    error,
    loadChats,
    loadMessages,
    sendMessage,
    startNewChat,
    stopStreaming,
    deleteChat,
  } = useChat()

  const [input, setInput] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    loadChats()
  }, [loadChats])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    sendMessage(text)
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleTextareaInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px'
    }
  }

  const handleSuggestion = (q: string) => {
    sendMessage(q)
  }

  const handleSelectChat = (chatId: string) => {
    loadMessages(chatId)
    setSidebarOpen(false)
  }

  const showEmptyState = !currentChatId && messages.length === 0

  return (
    <div className="flex h-full -mx-4 md:-mx-6 -my-4 md:-my-6">
      {/* Sidebar overlay on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Chat sidebar */}
      <aside
        className={`
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0 fixed lg:static inset-y-0 left-0 z-50 lg:z-auto
          w-64 bg-white border-r border-gray-200 flex flex-col transition-transform
        `}
      >
        <div className="p-3 border-b border-gray-100">
          <button
            onClick={() => { startNewChat(); setSidebarOpen(false) }}
            className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-brand-600 bg-brand-50 rounded-lg hover:bg-brand-100 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {chats.length === 0 && (
            <p className="px-4 py-3 text-xs text-gray-400">No conversations yet</p>
          )}
          {chats.map(chat => (
            <div
              key={chat.id}
              className={`group flex items-center gap-2 px-3 py-2 mx-2 rounded-lg cursor-pointer text-sm transition-colors ${
                currentChatId === chat.id
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
              onClick={() => handleSelectChat(chat.id)}
            >
              <MessageSquare className="h-3.5 w-3.5 shrink-0" />
              <span className="flex-1 truncate">{chat.title}</span>
              <button
                onClick={e => { e.stopPropagation(); deleteChat(chat.id) }}
                className="hidden group-hover:block p-1 text-gray-400 hover:text-red-500 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 text-gray-500 hover:text-gray-700"
          >
            <MessageSquare className="h-5 w-5" />
          </button>
          <span className="text-sm font-medium text-gray-700">Chat</span>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto">
          {showEmptyState ? (
            <EmptyState onSuggestion={handleSuggestion} />
          ) : (
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
              {messages.map(msg => (
                <MessageBubble key={msg.id} message={msg} />
              ))}
              {error && (
                <div className="px-4 py-3 bg-red-50 text-red-700 text-sm rounded-lg border border-red-200">
                  {error}
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="border-t border-gray-200 bg-white px-4 py-3">
          <div className="max-w-3xl mx-auto flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onInput={handleTextareaInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your expenses..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
            {isStreaming ? (
              <button
                onClick={stopStreaming}
                className="shrink-0 p-2.5 rounded-xl bg-gray-200 text-gray-600 hover:bg-gray-300 transition-colors"
                title="Stop"
              >
                <Square className="h-4 w-4" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="shrink-0 p-2.5 rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                title="Send"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}


function EmptyState({ onSuggestion }: { onSuggestion: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      <div className="w-14 h-14 rounded-2xl bg-brand-50 flex items-center justify-center mb-4">
        <Bot className="h-7 w-7 text-brand-600" />
      </div>
      <h2 className="text-lg font-semibold text-gray-800 mb-1">FinyBot Chat</h2>
      <p className="text-sm text-gray-500 mb-6 text-center max-w-md">
        Ask questions about your credit card transactions, spending patterns, and statements.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {SUGGESTED_QUESTIONS.map(q => (
          <button
            key={q}
            onClick={() => onSuggestion(q)}
            className="text-left px-4 py-3 text-sm text-gray-600 bg-white rounded-xl border border-gray-200 hover:border-brand-300 hover:bg-brand-50 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}


function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-4 py-2.5 rounded-2xl rounded-br-md bg-brand-600 text-white text-sm">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-7 h-7 rounded-full bg-brand-50 flex items-center justify-center mt-1">
        <Bot className="h-4 w-4 text-brand-600" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        {/* Tool call cards */}
        {message.toolCalls?.map((tc, i) => (
          <ToolCallCard key={`${tc.name}-${i}`} toolCall={tc} />
        ))}

        {/* Text content */}
        {message.content && (
          <div className="prose prose-sm max-w-none text-gray-800">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Loading state: has tool calls but no content yet */}
        {!message.content && message.toolCalls && message.toolCalls.length > 0 &&
          message.toolCalls.every(tc => tc.result !== null) && (
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Thinking...
            </div>
          )}
      </div>
    </div>
  )
}


function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false)
  const isLoading = toolCall.result === null

  const toolLabel: Record<string, string> = {
    search_transactions: 'Search Transactions',
    get_spending_summary: 'Spending Summary',
    get_statements: 'Statement Lookup',
    list_card_providers: 'List Cards',
  }

  const argSummary = Object.entries(toolCall.arguments)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
    .join(' · ')

  return (
    <div className="bg-white rounded-xl border border-gray-200 text-sm overflow-hidden">
      <button
        onClick={() => !isLoading && setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-gray-50 transition-colors"
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 text-brand-500 animate-spin shrink-0" />
        ) : (
          <Wrench className="h-3.5 w-3.5 text-gray-400 shrink-0" />
        )}
        <span className="font-medium text-gray-700">
          {toolLabel[toolCall.name] || toolCall.name}
        </span>
        {argSummary && (
          <span className="text-gray-400 truncate text-xs">{argSummary}</span>
        )}
        <span className="ml-auto shrink-0">
          {!isLoading && (
            expanded
              ? <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
              : <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
          )}
        </span>
      </button>

      {/* Result summary line */}
      {toolCall.result && !expanded && (
        <div className="px-3 pb-2 text-xs text-gray-500 truncate">
          {toolCall.result}
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-100 px-3 py-2 space-y-2">
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1">Arguments</p>
            <pre className="text-xs bg-gray-50 rounded-lg p-2 overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Result</p>
              <pre className="text-xs bg-gray-50 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap">
                {toolCall.result}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
