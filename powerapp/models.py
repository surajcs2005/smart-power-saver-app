from django.db import models
from django.utils import timezone

class Device(models.Model):
    name = models.CharField(max_length=100)
    is_on = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    room = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name

class PowerLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='logs')
    timestamp = models.DateTimeField(default=timezone.now)
    power_watts = models.FloatField()

    def __str__(self):
        return f"{self.device.name} - {self.power_watts}W"
