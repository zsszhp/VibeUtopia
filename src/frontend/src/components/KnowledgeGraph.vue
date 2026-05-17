<template>
  <div class="knowledge-graph">
    <div class="graph-header">
      <h3 class="section-title">知识图谱</h3>
      <div class="graph-stats" v-if="overview.connected">
        <span class="stat">{{ overview.node_count }} 节点</span>
        <span class="stat">{{ overview.edge_count }} 边</span>
      </div>
      <NTag v-else size="tiny" type="warning" round>未连接</NTag>
    </div>

    <!-- 搜索 -->
    <div class="search-bar">
      <NInput
        v-model:value="searchQuery"
        placeholder="搜索实体..."
        size="tiny"
        clearable
        @keyup.enter="searchEntity"
      />
    </div>

    <!-- D3力导向图 -->
    <div class="graph-container" ref="graphContainer">
      <svg ref="svgEl" class="graph-svg"></svg>
      <div v-if="!overview.connected" class="graph-placeholder">
        <p>图谱服务未连接</p>
        <p class="hint">请确保 Neo4j 服务已启动</p>
      </div>
    </div>

    <!-- 实体详情弹窗 -->
    <div v-if="selectedEntity" class="entity-detail">
      <div class="detail-header">
        <span class="detail-title">{{ selectedEntity.name || selectedEntity.entity_id }}</span>
        <button class="close-btn" @click="selectedEntity = null">×</button>
      </div>
      <div class="detail-body">
        <div v-for="(value, key) in selectedEntity" :key="key" class="detail-row">
          <span class="detail-key">{{ key }}</span>
          <span class="detail-value">{{ value }}</span>
        </div>
      </div>
      <div class="detail-actions">
        <NButton size="tiny" type="primary" @click="loadNeighbors(selectedEntity.entity_id)">
          查看邻居
        </NButton>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { NInput, NButton, NTag } from 'naive-ui'
import * as d3 from 'd3'
import { v3Api } from '../api'

const graphContainer = ref<HTMLElement | null>(null)
const svgEl = ref<SVGSVGElement | null>(null)
const searchQuery = ref('')
const overview = ref<any>({ connected: false, node_count: 0, edge_count: 0 })
const selectedEntity = ref<any>(null)

const graphData = ref<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] })

let simulation: d3.Simulation<any, any> | null = null

async function fetchOverview() {
  try {
    const resp = await v3Api.getGraphOverview()
    overview.value = resp.data
  } catch {
    overview.value = { connected: false, node_count: 0, edge_count: 0 }
  }
}

async function searchEntity() {
  if (!searchQuery.value || !overview.value.connected) return
  try {
    const resp = await v3Api.getGraphNeighbors(searchQuery.value, 2)
    const data = resp.data
    if (data.nodes?.length) {
      graphData.value = { nodes: data.nodes, edges: data.edges || [] }
      renderGraph()
    }
  } catch {}
}

async function loadNeighbors(entityId: string) {
  try {
    const resp = await v3Api.getGraphNeighbors(entityId, 1)
    const data = resp.data
    if (data.nodes?.length) {
      graphData.value = { nodes: data.nodes, edges: data.edges || [] }
      renderGraph()
    }
  } catch {}
}

function renderGraph() {
  if (!svgEl.value || !graphData.value.nodes.length) return

  const svg = d3.select(svgEl.value)
  svg.selectAll('*').remove()

  const width = graphContainer.value?.clientWidth || 400
  const height = 300

  svg.attr('width', width).attr('height', height)

  const g = svg.append('g')

  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.3, 5])
    .on('zoom', (event) => {
      g.attr('transform', event.transform)
    })

  svg.call(zoom)

  const nodes = graphData.value.nodes.map((n: any) => ({
    id: n.entity_id || n.id || String(Math.random()),
    name: n.name || n.entity_id || '',
    ...n,
  }))

  const edges = graphData.value.edges.map((e: any) => ({
    source: e.source?.entity_id || e.source || '',
    target: e.target?.entity_id || e.target || '',
    type: e.type || '',
  }))

  const colorScale = d3.scaleOrdinal(d3.schemeCategory10)

  const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', '#333')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', 1)

  const node = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', 6)
    .attr('fill', (_d: any, i: number) => colorScale(String(i % 10)))
    .attr('stroke', '#0a0a0f')
    .attr('stroke-width', 1.5)
    .style('cursor', 'pointer')
    .on('click', (_event: MouseEvent, d: any) => {
      selectedEntity.value = d
    })
    .call(d3.drag<SVGCircleElement, any>()
      .on('start', (event: any, d: any) => {
        if (!event.active) simulation?.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event: any, d: any) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: any, d: any) => {
        if (!event.active) simulation?.alphaTarget(0)
        d.fx = null
        d.fy = null
      })
    )

  const label = g.append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text((d: any) => d.name?.slice(0, 6) || '')
    .attr('font-size', 9)
    .attr('fill', '#888')
    .attr('dx', 8)
    .attr('dy', 3)

  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(60))
    .force('charge', d3.forceManyBody().strength(-120))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(12))
    .on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node
        .attr('cx', (d: any) => d.x)
        .attr('cy', (d: any) => d.y)

      label
        .attr('x', (d: any) => d.x)
        .attr('y', (d: any) => d.y)
    })
}

onMounted(() => {
  fetchOverview()
})

onUnmounted(() => {
  simulation?.stop()
})
</script>

<style scoped>
.knowledge-graph {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title {
  font-size: 13px;
  color: #888;
  font-weight: 600;
  margin: 0;
}

.graph-stats {
  display: flex;
  gap: 8px;
}

.stat {
  font-size: 11px;
  color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  padding: 2px 6px;
  border-radius: 3px;
}

.search-bar {
  margin-bottom: 4px;
}

.graph-container {
  position: relative;
  width: 100%;
  height: 300px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  overflow: hidden;
}

.graph-svg {
  width: 100%;
  height: 100%;
}

.graph-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #555;
  font-size: 13px;
}

.graph-placeholder .hint {
  font-size: 11px;
  color: #444;
  margin-top: 4px;
}

.entity-detail {
  background: #12121a;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  padding: 8px;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.detail-title {
  font-size: 13px;
  color: #ccc;
  font-weight: 600;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}

.close-btn:hover {
  color: #ef4444;
}

.detail-body {
  max-height: 120px;
  overflow-y: auto;
}

.detail-row {
  display: flex;
  gap: 8px;
  font-size: 11px;
  padding: 2px 0;
}

.detail-key {
  color: #6366f1;
  min-width: 80px;
}

.detail-value {
  color: #aaa;
  word-break: break-all;
}

.detail-actions {
  margin-top: 6px;
}
</style>
