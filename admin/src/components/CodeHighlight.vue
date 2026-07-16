<template>
  <div class="code-block" :class="{ 'dark-theme': isDark }">
    <div class="code-header">
      <span class="code-lang">{{ language }}</span>
      <el-button 
        size="small" 
        :type="copied ? 'success' : 'default'"
        @click="copyCode"
        class="copy-btn"
      >
        <el-icon><component :is="copied ? 'Check' : 'CopyDocument'" /></el-icon>
        {{ copied ? '已复制' : '复制' }}
      </el-button>
    </div>
    <pre><code v-html="highlightedCode"></code></pre>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Check } from '@element-plus/icons-vue'
import { useThemeStore } from '../stores/theme'

const props = defineProps({
  language: {
    type: String,
    default: 'javascript'
  },
  code: {
    type: String,
    required: true
  }
})

const themeStore = useThemeStore()
const isDark = computed(() => themeStore.isDark)
const copied = ref(false)

// 复制代码
const copyCode = async () => {
  try {
    // 优先使用现代 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(props.code)
    } else {
      // 降级方案：使用 execCommand
      const textarea = document.createElement('textarea')
      textarea.value = props.code
      textarea.style.position = 'fixed'
      textarea.style.opacity = '0'
      document.body.appendChild(textarea)
      textarea.select()
      
      const successful = document.execCommand('copy')
      document.body.removeChild(textarea)
      
      if (!successful) {
        throw new Error('execCommand copy failed')
      }
    }
    
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败，请手动复制')
  }
}

// 简单的代码高亮（不依赖外部库）
const highlightedCode = computed(() => {
  let code = props.code
  
  // 转义 HTML
  code = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  
  // Python 高亮
  if (props.language === 'python') {
    // 关键字
    code = code.replace(/\b(import|from|def|class|if|else|elif|for|while|return|try|except|finally|with|as|pass|break|continue|in|not|and|or|is|True|False|None)\b/g, '<span class="keyword">$1</span>')
    // 字符串
    code = code.replace(/('.*?'|".*?")/g, '<span class="string">$1</span>')
    // 注释
    code = code.replace(/(#.*)/g, '<span class="comment">$1</span>')
    // 函数调用
    code = code.replace(/\b(\w+)(?=\()/g, '<span class="function">$1</span>')
    // 数字
    code = code.replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
  }
  
  // JavaScript 高亮
  if (props.language === 'javascript') {
    // 关键字
    code = code.replace(/\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|this|class|extends|import|export|from|async|await|try|catch|finally|throw|typeof|instanceof|in|of)\b/g, '<span class="keyword">$1</span>')
    // 字符串
    code = code.replace(/('.*?'|".*?"|`.*?`)/g, '<span class="string">$1</span>')
    // 注释
    code = code.replace(/(\/\/.*)/g, '<span class="comment">$1</span>')
    // 函数调用
    code = code.replace(/\b(\w+)(?=\()/g, '<span class="function">$1</span>')
    // 数字
    code = code.replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
    // 对象属性
    code = code.replace(/\.(\w+)/g, '.<span class="property">$1</span>')
  }
  
  // Java 高亮
  if (props.language === 'java') {
    // 关键字
    code = code.replace(/\b(public|private|protected|class|interface|extends|implements|import|package|return|if|else|for|while|do|switch|case|break|continue|new|this|super|static|final|void|int|long|double|float|boolean|String|Map|List|Set)\b/g, '<span class="keyword">$1</span>')
    // 字符串
    code = code.replace(/(".*?")/g, '<span class="string">$1</span>')
    // 注释
    code = code.replace(/(\/\/.*)/g, '<span class="comment">$1</span>')
    // 函数调用
    code = code.replace(/\b(\w+)(?=\()/g, '<span class="function">$1</span>')
    // 数字
    code = code.replace(/\b(\d+)\b/g, '<span class="number">$1</span>')
  }
  
  // Bash 高亮
  if (props.language === 'bash') {
    // 注释
    code = code.replace(/(#.*)/g, '<span class="comment">$1</span>')
    // 命令
    code = code.replace(/^(\w+)/gm, '<span class="function">$1</span>')
    // 参数
    code = code.replace(/(\s-\w+)/g, ' <span class="property">$1</span>')
    // 路径
    code = code.replace(/(\/\S*)/g, '<span class="string">$1</span>')
  }
  
  return code
})
</script>

<style scoped>
.code-block {
  margin: 10px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  border: 1px solid #e4e7ed;
  position: relative;
}

.code-block.dark-theme {
  background: #1e1e1e;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  border: 1px solid #333;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: #e8eaed;
  border-bottom: 1px solid #e4e7ed;
}

.dark-theme .code-header {
  background: #2d2d2d;
  border-bottom: 1px solid #333;
}

.code-lang {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  text-transform: uppercase;
  letter-spacing: 0;
}

.dark-theme .code-lang {
  color: #909399;
}

.copy-btn {
  padding: 4px 12px;
  font-size: 12px;
}

.code-block pre {
  margin: 0;
  padding: 16px;
  overflow-x: auto;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

.dark-theme .code-block pre {
  color: #d4d4d4;
}

.code-block code {
  font-family: inherit;
}

/* 语法高亮颜色 - 浅色主题 */
.keyword {
  color: #1890ff;
  font-weight: bold;
}

.dark-theme .keyword {
  color: #569cd6;
}

.string {
  color: #52c41a;
}

.dark-theme .string {
  color: #ce9178;
}

.comment {
  color: #8c8c8c;
  font-style: italic;
}

.dark-theme .comment {
  color: #6a9955;
}

.function {
  color: #722ed1;
  font-weight: 600;
}

.dark-theme .function {
  color: #dcdcaa;
}

.number {
  color: #fa8c16;
}

.dark-theme .number {
  color: #b5cea8;
}

.property {
  color: #13c2c2;
}

.dark-theme .property {
  color: #9cdcfe;
}
</style>
