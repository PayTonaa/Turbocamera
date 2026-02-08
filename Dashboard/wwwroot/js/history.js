const container = document.getElementById('history-container');
const tbody = document.getElementById('hist');

let offset = null;
const limit = 20;
let isLoading = false;
let allLoaded = false;

function loadHistory() {
    if (isLoading || allLoaded) return;
    isLoading = true;

    let url = `/measurement?count=${limit}`;
    if (offset !== null) {
        url += `&offset=${offset}`;
    }

    fetch(url)
        .then(r => r.json())
        .then(data => {
            const records = data.records;
            if (records.length === 0) {
                allLoaded = true;
                isLoading = false;
                return;
            }

            let html = "";
            records.forEach(row => {
                const time = new Date(row.timestamp).toLocaleString('pl-PL');
                html += `<tr><td>${time}</td><td>${row.temperature}</td><td>${row.distance}</td></tr>`;
                offset = row.id;
            });
            tbody.insertAdjacentHTML('beforeend', html);

            if (records.length < limit)
                allLoaded = true;

            isLoading = false;
        })
        .catch(err => {
            console.error('Error fetching history:', err);
            isLoading = false;
        });
}

loadHistory();

if (container) {
    container.addEventListener('scroll', () => {
        if (container.scrollTop + container.clientHeight >= container.scrollHeight - 5) {
            loadHistory();
        }
    });
}
