(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var success = style.getPropertyValue('--success').trim();
  var warning = style.getPropertyValue('--warning').trim();

  // --- Chart: 功能完成度 ---
  var chartCompletion = echarts.init(document.getElementById('chart-completion'), null, { renderer: 'svg' });
  chartCompletion.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      formatter: function(params) {
        var data = params[0];
        return data.name + '<br/>完成度: <strong>' + data.value + '%</strong>';
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: [
        '聊天界面',
        '智能体配置',
        '模型配置',
        '对话持久化',
        '文件操作',
        '智能体调度',
        '权限控制',
        'Markdown渲染',
        '流式输出',
        '工具调用',
        '上下文记忆'
      ],
      axisLabel: {
        color: muted,
        fontSize: 12,
        interval: 0,
        rotate: 30
      },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      max: 100,
      axisLabel: {
        color: muted,
        formatter: '{value}%'
      },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: 100, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) } },
          { value: 100, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) } },
          { value: 100, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) } },
          { value: 100, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) } },
          { value: 100, itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: accent }, { offset: 1, color: accent2 }]) } },
          { value: 60, itemStyle: { color: warning } },
          { value: 40, itemStyle: { color: warning } },
          { value: 0, itemStyle: { color: '#e2e8f0' } },
          { value: 0, itemStyle: { color: '#e2e8f0' } },
          { value: 0, itemStyle: { color: '#e2e8f0' } },
          { value: 0, itemStyle: { color: '#e2e8f0' } }
        ],
        barWidth: '50%',
        itemStyle: {
          borderRadius: [6, 6, 0, 0]
        },
        label: {
          show: true,
          position: 'top',
          color: ink,
          fontSize: 11,
          fontWeight: 600,
          formatter: '{c}%'
        }
      }
    ],
    animation: false
  });
  window.addEventListener('resize', function() { chartCompletion.resize(); });
})();