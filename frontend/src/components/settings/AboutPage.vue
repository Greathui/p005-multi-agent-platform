<template>
  <div class="about-page">
    <!-- 项目介绍 -->
    <section class="about-section">
      <div class="section-icon">🤖</div>
      <h3 class="section-title">关于本软件</h3>
      <p class="section-text">
        这是一个多智能体团队协作平台，用户通过主智能体（项目经理角色）调度不同 AI 智能体协作完成复杂任务。
        面向非程序员个人用户，界面类似微信聊天框，支持本地单机部署。
      </p>
      <div class="tech-stack">
        <span class="tech-tag">Python + FastAPI</span>
        <span class="tech-tag">Vue 3 + Pinia</span>
        <span class="tech-tag">Element Plus</span>
        <span class="tech-tag">纯 JSON 文件存储</span>
      </div>
    </section>

    <el-divider />

    <!-- 捐赠打赏 -->
    <section class="about-section donate-section">
      <div class="section-icon">💖</div>
      <h3 class="section-title">支持开发者</h3>
      <p class="section-text">
        本软件由个人开发者独立维护，完全免费开源。如果觉得好用，欢迎打赏支持，让开发者有动力持续迭代新功能。
      </p>
      <p class="donate-hint">打赏金额随意，1 元也是鼓励～</p>

      <div class="donate-cards">
        <div class="donate-card">
          <div class="donate-card-header">
            <span class="donate-icon alipay">支</span>
            <span class="donate-name">支付宝</span>
          </div>
          <div class="donate-qr-wrapper">
            <img
              v-if="!alipayQrError"
              :src="'/alipay-qr.jpg'"
              alt="支付宝收款码"
              class="donate-qr-img"
              @error="alipayQrError = true"
            />
            <div v-else class="qr-box qr-placeholder">
              <div class="qr-pattern"></div>
              <div class="qr-tip">支付宝收款码<br/><small>放入 alipay-qr.jpg 即显示</small></div>
            </div>
          </div>
          <div class="donate-card-footer">扫码支持开发者</div>
        </div>

        <div class="donate-card">
          <div class="donate-card-header">
            <span class="donate-icon wechat">微</span>
            <span class="donate-name">微信</span>
          </div>
          <div class="donate-qr-wrapper">
            <img
              v-if="!wechatQrError"
              :src="'/wechat-qr.jpg'"
              alt="微信收款码"
              class="donate-qr-img"
              @error="wechatQrError = true"
            />
            <div v-else class="qr-box qr-placeholder">
              <div class="qr-pattern"></div>
              <div class="qr-tip">微信收款码<br/><small>放入 wechat-qr.jpg 即显示</small></div>
            </div>
          </div>
          <div class="donate-card-footer">扫码支持开发者</div>
        </div>
      </div>

      <div class="donate-note">
        <span class="note-icon">💡</span>
        <span>将收款码图片命名为 <code>alipay-qr.jpg</code> / <code>wechat-qr.jpg</code> 放到 <code>frontend/public/</code> 目录下，刷新页面即可显示。</span>
      </div>
    </section>

    <el-divider />

    <!-- 使用说明 -->
    <section class="about-section">
      <div class="section-icon">📖</div>
      <h3 class="section-title">快速上手</h3>
      <ol class="usage-list">
        <li>在「设置 → 模型配置」中添加你的大模型 API 配置（支持 OpenAI、通义千问、DeepSeek 等）</li>
        <li>在侧边栏创建团队和项目，每个项目都有独立的智能体团队</li>
        <li>在项目对话中和主智能体对话，它会自动调度子智能体协作完成任务</li>
        <li>任务完成后，成果会归档到项目的 <code>deliverables/</code> 目录</li>
      </ol>
    </section>

    <el-divider />

    <!-- 反馈与联系 -->
    <section class="about-section">
      <div class="section-icon">📮</div>
      <h3 class="section-title">反馈与建议</h3>
      <p class="section-text">
        如果遇到 bug 或有功能建议，欢迎通过以下方式反馈：
      </p>
      <ul class="feedback-list">
        <li>在软件使用中遇到问题，可以截图和描述问题现象</li>
        <li>有功能建议或改进想法，也欢迎提出</li>
      </ul>
    </section>

    <div class="about-footer">
      <span>P005 多智能体协作系统</span>
      <span class="footer-dot">·</span>
      <span>个人开发者维护</span>
      <span class="footer-dot">·</span>
      <span>感谢使用</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

// 收款码图片加载状态（图片不存在时 @error 触发，回退到占位提示）
const alipayQrError = ref(false)
const wechatQrError = ref(false)
</script>

<style scoped>
.about-page {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-bottom: 20px;
}

.about-section {
  padding: 4px 0;
}

.section-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 10px;
}

.section-text {
  font-size: 13px;
  color: #475569;
  line-height: 1.7;
  margin: 0 0 12px;
}

.tech-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.tech-tag {
  font-size: 12px;
  padding: 4px 10px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  color: #6366f1;
  border-radius: 9999px;
  font-weight: 500;
}

/* 捐赠区域 */
.donate-section {
  background: linear-gradient(135deg, rgba(254, 243, 199, 0.3) 0%, rgba(252, 231, 243, 0.3) 100%);
  border-radius: 12px;
  padding: 20px;
  margin: 4px 0;
}

.donate-hint {
  font-size: 13px;
  color: #92400e;
  margin: 8px 0 16px;
  font-weight: 500;
}

.donate-cards {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}

.donate-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 180px;
  transition: all 0.3s ease;
}

.donate-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
}

.donate-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.donate-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.donate-icon.alipay {
  background: #1677ff;
}

.donate-icon.wechat {
  background: #07c160;
}

.donate-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.donate-qr-wrapper {
  margin-bottom: 10px;
  width: 150px;
  height: 150px;
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.donate-qr-img {
  width: 150px;
  height: 150px;
  object-fit: cover;
  border-radius: 10px;
  display: block;
}

.qr-box {
  width: 150px;
  height: 150px;
  border-radius: 10px;
  background: #f8fafc;
  border: 2px dashed #cbd5e1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  position: relative;
  overflow: hidden;
}

.qr-pattern {
  width: 100px;
  height: 100px;
  background-image:
    linear-gradient(45deg, #cbd5e1 25%, transparent 25%),
    linear-gradient(-45deg, #cbd5e1 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #cbd5e1 75%),
    linear-gradient(-45deg, transparent 75%, #cbd5e1 75%);
  background-size: 12px 12px;
  background-position: 0 0, 0 6px, 6px -6px, -6px 0px;
  opacity: 0.4;
  border-radius: 4px;
}

.qr-tip {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
  position: relative;
  z-index: 1;
}

.donate-card-footer {
  font-size: 12px;
  color: #64748b;
}

.donate-note {
  margin-top: 16px;
  padding: 10px 14px;
  background: rgba(255, 251, 235, 0.8);
  border-radius: 8px;
  font-size: 12px;
  color: #92400e;
  line-height: 1.6;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.donate-note code {
  background: rgba(146, 64, 14, 0.1);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
  color: #78350f;
}

.note-icon {
  flex-shrink: 0;
}

/* 使用说明 */
.usage-list {
  font-size: 13px;
  color: #475569;
  line-height: 1.9;
  padding-left: 20px;
  margin: 0;
}

.usage-list li {
  margin-bottom: 4px;
}

.usage-list code {
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
  color: #6366f1;
}

/* 反馈列表 */
.feedback-list {
  font-size: 13px;
  color: #475569;
  line-height: 1.8;
  padding-left: 20px;
  margin: 0;
}

/* 底部 */
.about-footer {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
  text-align: center;
  font-size: 12px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.footer-dot {
  color: #cbd5e1;
}
</style>
