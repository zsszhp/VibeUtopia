<template>
  <div class="propagation-graph">
    <div v-if="!simulationData?.nodes?.length" class="empty-state">
      <span>暂无传播推演数据</span>
    </div>
    <div v-else ref="containerRef" class="graph-container"></div>
    <div v-if="hoveredNode" class="tooltip" :style="tooltipStyle">
      <div class="tooltip-name">{{ hoveredNode.name }}</div>
      <div class="tooltip-row">
        <span class="tooltip-label">阵营:</span>
        <span class="tooltip-value" :class="hoveredNode.faction">{{ factionLabel[hoveredNode.faction] }}</span>
      </div>
      <div class="tooltip-row">
        <span class="tooltip-label">影响力:</span>
        <span class="tooltip-value">{{ (hoveredNode.influence * 100).toFixed(0) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import type { SimulationData } from '../api'

const props = defineProps<{
  simulationData?: SimulationData
}>()

const containerRef = ref<HTMLElement>()
const hoveredNode = ref<any>(null)
const tooltipStyle = ref<Record<string, string>>({})

const factionLabel: Record<string, string> = {
  support: '支持',
  oppose: '反对',
  neutral: '中立',
}

const factionColor: Record<string, string> = {
  support: '#6366f1',
  oppose: '#ef4444',
  neutral: '#888',
}

let svg: d3.Selection<SVGSVGElement, unknown, null, undefined> | null = null
let simulation: d3.Simulation<d3.SimulationNodeDatum, undefined> | null = null

function render() {
  if (!containerRef.value || !props.simulationData?.nodes?.length) return

  d3.select(containerRef.value).selectAll('*').remove()

  const width = containerRef.value.clientWidth
  const height = 280

  svg = d3.select(containerRef.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)

  const g = svg.append('g')

  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.3, 4])
    .on('zoom', (event) => {
      g.attr('transform', event.transform.toString())
    })

  svg.call(zoom)

  const nodes = props.simulationData.nodes.map(n => ({ ...n }))
  const edges = props.simulationData.edges.map(e => ({ ...e }))

  simulation = d3.forceSimulation(nodes as d3.SimulationNodeDatum[])
    .force('link', d3.forceLink(edges)
      .id((d: any) => d.id)
      .distance(80)
    )
    .force('charge', d3.forceManyBody().strength(-200))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius((d: any) => (d.influence || 0.1) * 30 + 8))

  const link = g.append('g')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('stroke', '#2a2a3e')
    .attr('stroke-width', (d: any) => Math.max(1, d.strength * 6))
    .attr('stroke-opacity', 0.6)

  const node = g.append('g')
    .selectAll('circle')
    .data(nodes)
    .join('circle')
    .attr('r', (d: any) => (d.influence || 0.1) * 20 + 5)
    .attr('fill', (d: any) => factionColor[d.faction] || '#888')
    .attr('fill-opacity', 0.8)
    .attr('stroke', (d: any) => factionColor[d.faction] || '#888')
    .attr('stroke-width', 1.5)
    .attr('stroke-opacity', 0.4)
    .attr('cursor', 'pointer')

  const label = g.append('g')
    .selectAll('text')
    .data(nodes)
    .join('text')
    .text((d: any) => d.name)
    .attr('font-size', 10)
    .attr('fill', '#aaa')
    .attr('text-anchor', 'middle')
    .attr('dy', (d: any) => (d.influence || 0.1) * 20 + 18)

  node
    .on('mouseover', (event: MouseEvent, d: any) => {
      hoveredNode.value = d
      const rect = containerRef.value!.getBoundingClientRect()
      tooltipStyle.value = {
        left: (event.clientX - rect.left + 12) + 'px',
        top: (event.clientY - rect.top - 10) + 'px',
      }
      d3.select(event.currentTarget as SVGCircleElement)
        .attr('fill-opacity', 1)
        .attr('stroke-opacity', 0.8)
    })
    .on('mouseout', (event: MouseEvent) => {
      hoveredNode.value = null
      d3.select(event.currentTarget as SVGCircleElement)
        .attr('fill-opacity', 0.8)
        .attr('stroke-opacity', 0.4)
    })
    .call(d3.drag<SVGCircleElement, any>()
      .on('start', (event, d) => {
        if (!event.active) simulation?.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event, d) => {
        if (!event.active) simulation?.alphaTarget(0)
        d.fx = null
        d.fy = null
      })
    )

  simulation.on('tick', () => {
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

function handleResize() {
  if (containerRef.value && props.simulationData?.nodes?.length) {
    render()
  }
}

onMounted(() => {
  nextTick(render)
  window.addEventListener('resize', handleResize)
})

watch(() => props.simulationData, () => {
  nextTick(render)
}, { deep: true })

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  simulation?.stop()
  simulation = null
  svg = null
})
</script>

<style scoped>
.propagation-graph {
  position: relative;
}

.graph-container {
  width: 100%;
  height: 280px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
  overflow: hidden;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 120px;
  color: #444;
  font-size: 12px;
  background: #0a0a0f;
  border: 1px solid #1e1e2e;
  border-radius: 6px;
}

.tooltip {
  position: absolute;
  padding: 8px 10px;
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 6px;
  pointer-events: none;
  z-index: 100;
  font-size: 11px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.tooltip-name {
  font-weight: 600;
  color: #e0e0e0;
  margin-bottom: 4px;
}

.tooltip-row {
  display: flex;
  gap: 4px;
  margin-top: 2px;
}

.tooltip-label {
  color: #888;
}

.tooltip-value {
  color: #ccc;
  font-weight: 600;
}

.tooltip-value.support { color: #6366f1; }
.tooltip-value.oppose { color: #ef4444; }
.tooltip-value.neutral { color: #888; }
</style>
