using Microsoft.EntityFrameworkCore;

namespace Dashboard;

public class DataContext(DbContextOptions<DataContext> options) : DbContext(options)
{
    public required DbSet<MeasurementData> Measurements { get; set; }
}

public record MeasurementData(long Id, DateTime Timestamp, double Temperature, int Distance);
