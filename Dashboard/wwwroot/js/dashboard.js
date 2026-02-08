function update() {
    fetch('/measurement')
        .then(r => r.json())
        .then(d => {
            const records = d.records
            if (records.length == 0)
                return;

            const measurement = records[0]
            document.getElementById('temp').innerText = measurement.temperature;
            document.getElementById('dist').innerText = measurement.distance;
            alarm = measurement.temperature >= 38;
            document.getElementById('status').innerText = alarm ? "ALARM" : "OK";
            document.getElementById('status').className = alarm ? "status-alarm" : "status-ok";
        })
        .catch(err => console.error('Error fetching data:', err));
}

setInterval(update, 1000);
update();
