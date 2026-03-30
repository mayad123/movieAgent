import { getProjects, getProject, createProject } from './modules/api.js';

const listEl = document.getElementById('projectsList');
const assetsEl = document.getElementById('projectAssetsGrid');
const titleEl = document.getElementById('projectTitle');
const subtitleEl = document.getElementById('projectSubtitle');
const createForm = document.getElementById('projectsCreateForm');
const projectNameInput = document.getElementById('projectNameInput');
const projectFocusInput = document.getElementById('projectFocusInput');
const projectDescriptionInput = document.getElementById('projectDescriptionInput');

let projects = [];
let activeProjectId = null;

function formatAssetSubtitle(asset) {
    const focus = (asset && asset.pageId) ? ('pageId: ' + asset.pageId) : '';
    const conv = (asset && asset.conversationId) ? ('conversation: ' + asset.conversationId) : '';
    return [focus, conv].filter(Boolean).join(' · ');
}

function renderAssets(project) {
    assetsEl.innerHTML = '';
    if (!project) return;
    const assets = Array.isArray(project.assets) ? project.assets : [];
    if (assets.length === 0) {
        const p = document.createElement('p');
        p.textContent = 'No assets in this project yet. Use Add to Collection with project scope in chat.';
        assetsEl.appendChild(p);
        return;
    }
    assets.forEach(function (asset) {
        const card = document.createElement('article');
        card.className = 'projects-asset-card';
        const img = document.createElement('img');
        img.src = asset.posterImageUrl || asset.storedRef || '';
        img.alt = asset.title || 'Movie';
        card.appendChild(img);
        const meta = document.createElement('div');
        meta.className = 'projects-asset-meta';
        const name = document.createElement('strong');
        name.textContent = asset.title || 'Untitled';
        const sub = document.createElement('div');
        sub.textContent = formatAssetSubtitle(asset);
        meta.appendChild(name);
        meta.appendChild(sub);
        card.appendChild(meta);
        assetsEl.appendChild(card);
    });
}

function renderProjectList() {
    listEl.innerHTML = '';
    projects.forEach(function (project) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'projects-list-item' + (project.id === activeProjectId ? ' active' : '');
        const strong = document.createElement('strong');
        strong.textContent = project.name || 'Untitled';
        const br = document.createElement('br');
        const small = document.createElement('small');
        small.textContent = ((project.contextFocus || project.description || '').trim() || 'No focus yet');
        btn.appendChild(strong);
        btn.appendChild(br);
        btn.appendChild(small);
        btn.addEventListener('click', function () {
            loadProjectDetail(project.id);
        });
        listEl.appendChild(btn);
    });
}

async function loadProjectDetail(projectId) {
    activeProjectId = projectId;
    renderProjectList();
    try {
        const project = await getProject(projectId, { timeoutMs: 12000 });
        titleEl.textContent = project.name || 'Untitled';
        const bits = [];
        if (project.contextFocus) bits.push('Focus: ' + project.contextFocus);
        if (project.description) bits.push(project.description);
        subtitleEl.textContent = bits.join(' · ');
        renderAssets(project);
    } catch (_) {
        titleEl.textContent = 'Project unavailable';
        subtitleEl.textContent = 'Could not load this project.';
        assetsEl.innerHTML = '';
    }
}

async function loadProjectsIndex() {
    try {
        projects = await getProjects({ timeoutMs: 12000 });
    } catch (_) {
        projects = [];
    }
    renderProjectList();
    if (projects.length > 0) {
        await loadProjectDetail(activeProjectId || projects[0].id);
    } else {
        titleEl.textContent = 'No projects yet';
        subtitleEl.textContent = 'Create your first project to group movies by genre, theme, or interest.';
        assetsEl.innerHTML = '';
    }
}

createForm.addEventListener('submit', async function (e) {
    e.preventDefault();
    const name = String(projectNameInput.value || '').trim();
    if (!name) return;
    try {
        const project = await createProject({
            name: name,
            contextFocus: String(projectFocusInput.value || '').trim() || null,
            description: String(projectDescriptionInput.value || '').trim() || null
        }, { timeoutMs: 12000 });
        projectNameInput.value = '';
        projectFocusInput.value = '';
        projectDescriptionInput.value = '';
        await loadProjectsIndex();
        if (project && project.id) {
            await loadProjectDetail(project.id);
        }
    } catch (_) {
        subtitleEl.textContent = 'Could not create project right now.';
    }
});

void loadProjectsIndex();
