using Dashboard;

using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

var services = builder.Services;

services.AddScoped<IMeasurementsManager, DefaultMeasurementsManager>();

services.AddSingleton(TimeProvider.System);

services.AddDbContext<DataContext>(options =>
{
    options.UseSqlite(builder.Configuration.GetConnectionString("Data"));
});

var app = builder.Build();

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapPost("/measurement", async (CreateMeasurementRequest data, IMeasurementsManager measurementsManager, TimeProvider timeProvider) =>
{
    await measurementsManager.AddMeasurementAsync(new(timeProvider.GetUtcNow(), data.Temperature, data.Distance));
    return Results.Created();
});

app.MapGet("/measurement", (IMeasurementsManager measurementsManager, [FromQuery] long? offset, [FromQuery] int count = 1) =>
{
    var measurements = measurementsManager.GetMeasurementsAsync(offset, count);

    return new GetMeasurementsResponse(measurements);
});

await using (var scope = app.Services.CreateAsyncScope())
    scope.ServiceProvider.GetRequiredService<DataContext>().Database.Migrate();

await app.RunAsync();

public record CreateMeasurementRequest(double Temperature, int Distance);

public record GetMeasurementsResponse(IAsyncEnumerable<MeasurementRecord> Records);
