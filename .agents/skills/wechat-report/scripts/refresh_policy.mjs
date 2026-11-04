/** One refresh decision shared by report readiness and source collection. */
export function dataRefreshRequested(text) {
 const positive=String(text??'').replace(/(?:不需要|无需|不要|不用|不必|不再|不|别)(?:再|去)?(?:重新查询|重新取数|重查数据|更新数据|刷新(?:数据)?|获取最新(?:数据)?)/g,'')
 const dataInstruction=positive.replace(/最新(?:的)?(?:图片|图表|排版|代码|脚本|样式|格式|成品)/g,'')
 return /最新|刷新|重新查询|重新取数|重查数据|更新数据/.test(dataInstruction)
}

export function collectionExecution(plan,turn) {
 const execution={freshness:'cache-ok',deadlineMs:360000,...plan.execution}
 if(turn?.schema==='plaza-report-turn/1' && turn.enabled && dataRefreshRequested(turn.requestText)) {
  execution.freshness='live';delete execution.snapshotId
 }
 return execution
}
