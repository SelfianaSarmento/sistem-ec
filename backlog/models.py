from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = [
        ('Solicitante', 'Solicitante'),
        ('Reviewer', 'Reviewer'),
        ('DES', 'Utilizadór 1 (DES)'),
        ('Admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Solicitante')
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class Release(models.Model):
    MAX_ECS_PER_RELEASE = 10

    release_code = models.CharField(max_length=20, unique=True)
    year = models.IntegerField()
    number_sequency = models.IntegerField()
    production_go_live_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-year', '-number_sequency']

    def is_open(self):
        return self.production_go_live_date is None

    def ec_count(self):
        return self.ecs.count()

    def is_full(self):
        return self.ec_count() >= self.MAX_ECS_PER_RELEASE

    def remaining_slots(self):
        return max(0, self.MAX_ECS_PER_RELEASE - self.ec_count())

    def __str__(self):
        return self.release_code

    @classmethod
    def generate_code(cls, year, seq):
        return f"TT_ON_{year}-{str(seq).zfill(3)}"


class ECS(models.Model):
    STATUS_CHOICES = [
        ('Em_Validasaun', 'Em Validasaun'),
        ('Aprovadu', 'Aprovadu'),
        ('Rejeitadu', 'Rejeitadu'),
        ('Enviadu_DES', 'Enviadu DES'),
        ('Fechadu', 'Fechadu'),
        ('Canceladu', 'Canceladu'),
    ]

    esc_code = models.CharField(max_length=15, unique=True)
    year = models.IntegerField()
    number_sequenci = models.IntegerField()
    cr_rt_me_reference = models.CharField(max_length=50)
    description = models.TextField()
    id_release = models.ForeignKey(Release, on_delete=models.PROTECT, related_name='ecs')
    id_solicitante = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ecs_criadas')
    cd_responsavel_id = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='ecs_reviewer',
        null=True, blank=True
    )
    creation_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Em_Validasaun')
    rejection_comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-year', '-number_sequenci']
        verbose_name = "EC"
        verbose_name_plural = "ECs"

    def __str__(self):
        return f"{self.esc_code} — {self.description[:50]}"


class DocumentVersion(models.Model):
    ec = models.ForeignKey(ECS, on_delete=models.CASCADE, related_name='versions')
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    version_number = models.CharField(max_length=10)
    file_path = models.FileField(upload_to='ec_documents/%Y/')
    upload_date = models.DateTimeField(auto_now_add=True)
    change_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.ec.esc_code} — {self.version_number}"


class AuditLog(models.Model):
    ec = models.ForeignKey(ECS, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    detail = models.TextField(blank=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_hora']

    def __str__(self):
        from django.utils import timezone
        dt = timezone.localtime(self.data_hora) if self.data_hora else None
        ts = dt.strftime('%d-%m-%Y %H:%M') if dt else '—'
        return f"{self.ec.esc_code} — {self.action} ({ts})"