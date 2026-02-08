namespace Dashboard;

public interface IMeasurementsManager
{
    public ValueTask AddMeasurementAsync(MeasurementProperties measurement);

    public IAsyncEnumerable<MeasurementRecord> GetMeasurementsAsync(long? offset, int count);
}

public record MeasurementProperties(DateTimeOffset Timestamp, double Temperature, int Distance);

public record MeasurementRecord(long Id, DateTimeOffset Timestamp, double Temperature, int Distance);
