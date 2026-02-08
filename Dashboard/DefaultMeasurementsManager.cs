using Microsoft.EntityFrameworkCore;

namespace Dashboard;

public class DefaultMeasurementsManager(DataContext dataContext) : IMeasurementsManager
{
    public ValueTask AddMeasurementAsync(MeasurementProperties measurement)
    {
        dataContext.Measurements.Add(new(default, measurement.Timestamp.ToUniversalTime().DateTime, measurement.Temperature, measurement.Distance));
        return new(dataContext.SaveChangesAsync());
    }

    public IAsyncEnumerable<MeasurementRecord> GetMeasurementsAsync(long? offset, int count)
    {
        var measurements = offset is { } offsetValue
            ? dataContext.Measurements.Where(m => m.Id < offsetValue)
            : dataContext.Measurements;

        return measurements
            .Where(m => m.Temperature >= 35.6 && m.Temperature <= 40)
            .OrderByDescending(m => m.Id)
            .Take(count)
            .Select(m => new MeasurementRecord(m.Id, m.Timestamp, m.Temperature, m.Distance))
            .AsAsyncEnumerable();
    }
}
