<script setup>
import { ref, computed, onMounted } from 'vue'

const actors = ref([]), actor = ref('alice@east.test'), courses = ref([]), course = ref('')
const items = ref([]), total = ref(0), page = ref(1), pageSize = 10
const search = ref(''), sort = ref('issue_date'), direction = ref('desc')
const loading = ref(false), error = ref(''), issuing = ref(false), exporting = ref(false)
const operation = ref(null), issueError = ref(''), exportError = ref(''), selected = ref(null)
const detailLoading = ref(false), detailError = ref(''), revoking = ref(false), confirmation = ref(false)
const pendingKey = ref(null), pendingCourse = ref(null)
let listVersion = 0
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

async function api(path, options = {}) {
  const response = await fetch('/api' + path, {...options, headers: {
    'X-Actor': actor.value, 'Content-Type': 'application/json', ...options.headers,
  }})
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status}).`)
  }
  return response
}

function filters() {
  return new URLSearchParams({search: search.value, sort: sort.value, direction: direction.value})
}

async function load() {
  const version = ++listVersion
  loading.value = true; error.value = ''
  try {
    const params = filters(); params.set('page', page.value); params.set('page_size', pageSize)
    const data = await (await api('/certificates?' + params)).json()
    if (version === listVersion) { items.value = data.items; total.value = data.total }
  } catch (e) { if (version === listVersion) { error.value = e.message; items.value = [] } }
  finally { if (version === listVersion) loading.value = false }
}

async function switchActor() {
  ++listVersion
  selected.value = null; confirmation.value = false; operation.value = null; issueError.value = ''
  exportError.value = ''; detailError.value = ''; pendingKey.value = null; pendingCourse.value = null
  courses.value = []; course.value = ''; items.value = []; page.value = 1
  try {
    courses.value = await (await api('/courses')).json()
    course.value = courses.value[0]?.id ?? ''
    await load()
  } catch (e) { error.value = e.message }
}

function applyFilters() { page.value = 1; load() }
function movePage(delta) { page.value += delta; load() }

async function issue() {
  if (issuing.value || !course.value) return
  issuing.value = true; issueError.value = ''; operation.value = null
  if (pendingCourse.value !== course.value || !pendingKey.value) {
    pendingKey.value = crypto.randomUUID(); pendingCourse.value = course.value
  }
  try {
    operation.value = await (await api('/bulk-issue', {
      method: 'POST', headers: {'Idempotency-Key': pendingKey.value},
      body: JSON.stringify({course_id: Number(course.value)}),
    })).json()
    pendingKey.value = null; pendingCourse.value = null
    await load()
  } catch (e) { issueError.value = e.message + ' Retry uses the same operation key.' }
  finally { issuing.value = false }
}

async function showDetail(id) {
  detailLoading.value = true; detailError.value = ''; selected.value = null; confirmation.value = false
  try { selected.value = await (await api('/certificates/' + id)).json() }
  catch (e) { detailError.value = e.message }
  finally { detailLoading.value = false }
}

async function revoke() {
  if (revoking.value || !selected.value || !confirmation.value) return
  revoking.value = true; detailError.value = ''
  const id = selected.value.id
  try {
    await api(`/certificates/${id}/revoke`, {method: 'POST'})
    await showDetail(id); await load()
  } catch (e) { detailError.value = e.message }
  finally { revoking.value = false }
}

async function exportCsv() {
  exporting.value = true; exportError.value = ''
  try {
    const response = await api('/certificates/export?' + filters())
    const url = URL.createObjectURL(await response.blob())
    const link = document.createElement('a'); link.href = url; link.download = 'certificates.csv'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 10000)
  } catch (e) { exportError.value = e.message }
  finally { exporting.value = false }
}

onMounted(async () => {
  try { actors.value = await (await api('/actors')).json(); await switchActor() }
  catch (e) { error.value = e.message }
})
</script>

<template>
  <main>
    <header><div><p class="eyebrow">TRAINING PLATFORM</p><h1>Certificate Admin</h1></div>
      <label>Acting administrator
        <select v-model="actor" @change="switchActor" :disabled="issuing || revoking || exporting || detailLoading">
          <option v-for="a in actors" :value="a.email" :key="a.email">{{ a.tenant }} · {{ a.email }}</option>
        </select>
      </label>
    </header>

    <section aria-labelledby="issue-title">
      <h2 id="issue-title">Bulk issue</h2>
      <p>Issue certificates to completed learners. Incomplete and previously certified learners are skipped.</p>
      <div class="controls"><label>Course<select v-model="course" :disabled="issuing"><option v-for="c in courses" :key="c.id" :value="c.id">{{ c.title }}</option></select></label>
        <button @click="issue" :disabled="issuing || !course">{{ issuing ? 'Issuing…' : 'Issue certificates' }}</button></div>
      <p v-if="issuing" role="status">Operation running. Please wait.</p>
      <p v-if="issueError" role="alert" class="error">{{ issueError }}</p>
      <div v-if="operation" role="status"><h3>Operation #{{ operation.operation_id }} · {{ operation.status }}</h3>
        <ul><li v-for="o in operation.outcomes" :key="o.learner_id">{{ o.learner_name }}: <strong>{{ o.outcome }}</strong><span v-if="o.reason"> — {{ o.reason }}</span></li></ul>
        <p v-if="!operation.outcomes.length">No enrollments in this course.</p>
      </div>
    </section>

    <section aria-labelledby="list-title">
      <div class="section-heading"><h2 id="list-title">Certificates</h2><button @click="exportCsv" :disabled="exporting">{{ exporting ? 'Exporting…' : 'Export CSV' }}</button></div>
      <form class="controls" @submit.prevent="applyFilters">
        <label>Search learner or serial<input v-model="search" maxlength="160" placeholder="Name or serial number"></label>
        <label>Sort by<select v-model="sort" @change="applyFilters"><option value="issue_date">Issue date (tenant local)</option><option value="learner_name">Learner</option><option value="course_title">Course</option><option value="serial_number">Serial number</option><option value="status">Status</option></select></label>
        <label>Direction<select v-model="direction" @change="applyFilters"><option value="desc">Descending</option><option value="asc">Ascending</option></select></label>
        <button type="submit">Search / refresh</button>
      </form>
      <p v-if="exportError" role="alert" class="error">{{ exportError }}</p>
      <p v-if="loading" role="status">Loading certificates…</p>
      <p v-else-if="error" role="alert" class="error">{{ error }} <button @click="load">Retry</button></p>
      <p v-else-if="!items.length">No certificates match your search.</p>
      <div v-else class="table-wrap"><table><thead><tr><th>Learner</th><th>Course</th><th>Serial number</th><th>Issue date (tenant local)</th><th>Status</th><th>Details</th></tr></thead>
        <tbody><tr v-for="c in items" :key="c.id"><td>{{ c.learner_name }}</td><td>{{ c.course_title }}</td><td class="serial">{{ c.serial_number }}</td><td>{{ c.issue_date }}</td><td><span :class="['badge', c.status === 'REVOKED' ? 'revoked' : '']">{{ c.status }}</span></td><td><button @click="showDetail(c.id)" :disabled="detailLoading || revoking">View</button></td></tr></tbody>
      </table></div>
      <nav aria-label="Pagination"><button @click="movePage(-1)" :disabled="page <= 1 || loading">Previous</button><span>Page {{ page }} of {{ pages }} · {{ total }} certificates</span><button @click="movePage(1)" :disabled="page >= pages || loading">Next</button></nav>
    </section>

    <section v-if="selected || detailLoading || detailError" aria-labelledby="detail-title">
      <h2 id="detail-title">Certificate detail</h2><p v-if="detailLoading" role="status">Loading detail…</p><p v-if="detailError" role="alert" class="error">{{ detailError }}</p>
      <template v-if="selected"><dl><dt>Serial number</dt><dd>{{ selected.serial_number }}</dd><dt>Learner</dt><dd>{{ selected.learner_name }}</dd><dt>Course</dt><dd>{{ selected.course_title }}</dd><dt>Issued (tenant local)</dt><dd>{{ selected.issued_local }} · {{ selected.timezone }}</dd><dt>Status</dt><dd>{{ selected.status }}</dd></dl>
        <button v-if="selected.status === 'ACTIVE' && !confirmation" @click="confirmation = true" :disabled="revoking">Revoke certificate</button>
        <div v-if="confirmation" role="alert"><p>Revoke this certificate? This cannot be undone.</p><button @click="revoke" :disabled="revoking">{{ revoking ? 'Revoking…' : 'Confirm revocation' }}</button> <button @click="confirmation = false" :disabled="revoking">Cancel</button></div>
        <h3>Audit history</h3><ul><li v-for="(event, i) in selected.audit_events" :key="i">{{ event.action }} · {{ event.actor }} · {{ event.occurred_at }}</li></ul>
      </template>
    </section>
  </main>
</template>
