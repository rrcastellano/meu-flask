
// ==================== Variáveis Globais ====================
let currentPage = 1;
let sortBy = 'data';
let sortDir = 'asc';
const pageSize = 20;

// ==================== Função para exibir Toast ====================
function showToast(message, type = 'success') {
    const toastContainer = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Fechar"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

// ==================== Função para carregar recargas ====================
async function loadRecharges() {
    const params = new URLSearchParams({
        page: currentPage,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: sortDir,
        local: document.getElementById('filter-local').value,
        observacoes: document.getElementById('filter-observacoes').value,
        isento: document.getElementById('filter-isento').value,
        date_from: document.getElementById('filter-date-from').value,
        date_to: document.getElementById('filter-date-to').value
    });

    try {
        const response = await fetch(`/api/manage_recharges?${params.toString()}`);
        if (!response.ok) throw new Error('Erro ao carregar recargas');
        const data = await response.json();

        const tbody = document.getElementById('recharges-body');
        tbody.innerHTML = '';

        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center">Nenhuma recarga encontrada.</td></tr>';
        } else {
            data.items.forEach(item => {
                const tr = document.createElement('tr');
                tr.dataset.id = item.id;
                tr.innerHTML = `
                    <td>${item.data}</td>
                    <td>${item.kwh}</td>
                    <td>R$ ${item.custo.toFixed(2)}</td>
                    <td>${item.isento ? 'Sim' : 'Não'}</td>
                    <td>${item.odometro}</td>
                    <td>${item.local || ''}</td>
                    <td title="${item.observacoes || ''}">${(item.observacoes || '').substring(0, 30)}${item.observacoes && item.observacoes.length > 30 ? '...' : ''}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary btn-edit">Editar</button>
                        <button class="btn btn-sm btn-outline-danger btn-delete">Excluir</button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        document.getElementById('pagination-info').textContent = `Exibindo ${(currentPage - 1) * pageSize + 1}–${Math.min(currentPage * pageSize, data.total)} de ${data.total}`;
        document.getElementById('btn-prev-page').disabled = !data.has_prev;
        document.getElementById('btn-next-page').disabled = !data.has_next;
    } catch (error) {
        showToast(error.message, 'danger');
    }
}

// ==================== Eventos de Filtros ====================
document.getElementById('btn-apply-filters').addEventListener('click', () => {
    currentPage = 1;
    loadRecharges();
});

document.getElementById('btn-clear-filters').addEventListener('click', () => {
    document.getElementById('filters-form').reset();
    currentPage = 1;
    loadRecharges();
});

document.getElementById('btn-last-30-days').addEventListener('click', () => {
    const today = new Date();
    const pastDate = new Date();
    pastDate.setDate(today.getDate() - 30);
    document.getElementById('filter-date-from').value = pastDate.toISOString().split('T')[0];
    document.getElementById('filter-date-to').value = today.toISOString().split('T')[0];
    currentPage = 1;
    loadRecharges();
});

// ==================== Paginação ====================
document.getElementById('btn-prev-page').addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        loadRecharges();
    }
});

document.getElementById('btn-next-page').addEventListener('click', () => {
    currentPage++;
    loadRecharges();
});

// ==================== Ordenação ====================
document.querySelectorAll('#recharges-table th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
        const field = th.dataset.sort;
        if (sortBy === field) {
            sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            sortBy = field;
            sortDir = 'asc';
        }
        loadRecharges();
    });
});

// ==================== Modal de Edição ====================
document.getElementById('recharges-body').addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-edit')) {
        const tr = e.target.closest('tr');
        const id = tr.dataset.id;
        document.getElementById('edit-id').value = id;
        document.getElementById('edit-data').value = tr.children[0].textContent;
        document.getElementById('edit-kwh').value = tr.children[1].textContent;
        document.getElementById('edit-custo').value = tr.children[2].textContent.replace('R$ ', '');
        document.getElementById('edit-isento').checked = tr.children[3].textContent === 'Sim';
        document.getElementById('edit-odometro').value = tr.children[4].textContent;
        document.getElementById('edit-local').value = tr.children[5].textContent;
        document.getElementById('edit-observacoes').value = tr.children[6].getAttribute('title');
        const editModal = new bootstrap.Modal(document.getElementById('editModal'));
        editModal.show();
    }
});

document.getElementById('btn-save-edit').addEventListener('click', async () => {
    const id = document.getElementById('edit-id').value;
    const payload = {
        data: document.getElementById('edit-data').value,
        kwh: parseFloat(document.getElementById('edit-kwh').value),
        custo: parseFloat(document.getElementById('edit-custo').value),
        odometro: parseFloat(document.getElementById('edit-odometro').value),
        isento: document.getElementById('edit-isento').checked,
        local: document.getElementById('edit-local').value,
        observacoes: document.getElementById('edit-observacoes').value
    };

    try {
        const response = await fetch(`/api/manage_recharges/${id}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Erro ao salvar edição');
        }

        showToast('Recarga atualizada com sucesso!', 'success');
        const editModal = bootstrap.Modal.getInstance(document.getElementById('editModal'));
        editModal.hide();
        loadRecharges();
    } catch (error) {
        showToast(error.message, 'danger');
    }
});

// ==================== Modal de Exclusão ====================
document.getElementById('recharges-body').addEventListener('click', (e) => {
    if (e.target.classList.contains('btn-delete')) {
        const tr = e.target.closest('tr');
        const id = tr.dataset.id;
        document.getElementById('btn-confirm-delete').dataset.id = id;
        const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
        deleteModal.show();
    }
});

document.getElementById('btn-confirm-delete').addEventListener('click', async () => {
    const id = document.getElementById('btn-confirm-delete').dataset.id;
    try {
        const response = await fetch(`/api/manage_recharges/${id}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').getAttribute('content')
            }
        });

        if (!response.ok) throw new Error('Erro ao excluir recarga');

        showToast('Recarga excluída com sucesso!', 'success');
        const deleteModal = bootstrap.Modal.getInstance(document.getElementById('deleteModal'));
        deleteModal.hide();
        loadRecharges();
    } catch (error) {
        showToast(error.message, 'danger');
    }
});


// ==================== Botão Exportar CSV ====================    
/*
document.addEventListener('DOMContentLoaded', () => {
    const btnExport = document.getElementById('btn-export');
    if (!btnExport) return; // evita erro se o botão não existir

    btnExport.addEventListener('click', (e) => {
        e.preventDefault(); // evita submit do form
        const params = new URLSearchParams({
            local: document.getElementById('filter-local')?.value || '',
            observacoes: document.getElementById('filter-observacoes')?.value || '',
            isento: document.getElementById('filter-isento')?.value || 'all',
            date_from: document.getElementById('filter-date-from')?.value || '',
            date_to: document.getElementById('filter-date-to')?.value || ''
        });
        window.location.href = `/export_recharges?${params.toString()}`;
    });
});
*/

document.addEventListener('DOMContentLoaded', () => {
  const btnExport = document.getElementById('btn-export');
  if (!btnExport) return;

  btnExport.setAttribute('type', 'button'); // evita submit do form
  btnExport.addEventListener('click', (e) => {
    e.preventDefault();

    const getVal = (id) => document.getElementById(id)?.value || '';
    const params = new URLSearchParams({
      local:       getVal('filter-local'),
      observacoes: getVal('filter-observacoes'),
      isento:      getVal('filter-isento') || 'all',
      date_from:   getVal('filter-date-from'),
      date_to:     getVal('filter-date-to')
    });

    window.location.href = `/export_recharges?${params.toString()}`;
  });
});


// ==================== Inicialização ====================
document.addEventListener('DOMContentLoaded', () => {
    loadRecharges();
});
