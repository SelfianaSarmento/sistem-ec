from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import User, Release, ECS, DocumentVersion, AuditLog
from datetime import date


def log_action(ec, user, action, detail=""):
    AuditLog.objects.create(ec=ec, user=user, action=action, detail=detail)


@login_required
def dashboard(request):
    user = request.user
    role = user.role
    context = {'role': role}

    if role == 'Solicitante':
        context['ecs'] = ECS.objects.filter(id_solicitante=user).order_by('-creation_date')[:5]
    elif role == 'Reviewer':
        context['ecs'] = ECS.objects.filter(cd_responsavel_id=user, status='Em_Validasaun')[:5]
    elif role == 'DES':
        context['ecs'] = ECS.objects.filter(status__in=['Aprovadu', 'Enviadu_DES'])[:5]
    elif role == 'Admin':
        context['ecs'] = ECS.objects.all().order_by('-creation_date')[:5]

    context['total'] = ECS.objects.count()
    context['em_validasaun'] = ECS.objects.filter(status='Em_Validasaun').count()
    context['aprovadu'] = ECS.objects.filter(status__in=['Aprovadu','Fechadu']).count()
    context['rejeitadu'] = ECS.objects.filter(status='Rejeitadu').count()
    return render(request, 'backlog/dashboard.html', context)


@login_required
def backlog_list(request):
    from django.db.models import Q
    user = request.user
    role = user.role
    ecs = ECS.objects.select_related('id_solicitante', 'cd_responsavel_id', 'id_release').all()

    if role == 'Solicitante':
        ecs = ecs.filter(id_solicitante=user)
    elif role == 'Reviewer':
        ecs = ecs.filter(cd_responsavel_id=user)
    elif role == 'DES':
        ecs = ecs.filter(status__in=['Aprovadu', 'Enviadu_DES', 'Fechadu'])

    # filter
    status_filter = request.GET.get('status')
    if status_filter:
        ecs = ecs.filter(status=status_filter)

    q = request.GET.get('q', '').strip()
    if q:
        # busca tuir inisiál — ex: "g" → hotu ne'ebe ko'alia husi "g" mak aparese
        ecs = ecs.filter(
            Q(esc_code__istartswith=q) | Q(cr_rt_me_reference__istartswith=q) |
            Q(description__istartswith=q)
        )

    ecs = ecs.order_by('-year', '-number_sequenci')
    return render(request, 'backlog/backlog_list.html', {
        'ecs': ecs, 'role': role,
        'status_choices': ECS.STATUS_CHOICES,
        'status_filter': status_filter or '',
        'q': q,
    })


@login_required
def ec_create(request):
    if request.user.role != 'Solicitante':
        messages.error(request, 'Ita la iha permisaun.')
        return redirect('dashboard')

    if request.method == 'POST':
        ref = request.POST.get('cr_rt_me_reference')
        desc = request.POST.get('description')
        release_id = request.POST.get('release')
        reviewer_id = request.POST.get('reviewer')
        file = request.FILES.get('document')

        # generate esc_code
        year = date.today().year
        last = ECS.objects.filter(year=year).order_by('-number_sequenci').first()
        seq = (last.number_sequenci + 1) if last else 1
        esc_code = f"EC{year}{str(seq).zfill(3)}"

        # release (batas: max 10 EC per release, ex: TT_ON_2026-001 penuh 10 -> tutup, pake 002, 003, dst)
        # jumlah release per tahun unlimited, solicitante bebas pilih release aberta mana saja
        if release_id == 'nova':
            last_rel = Release.objects.filter(year=year).order_by('-number_sequency').first()
            rel_seq = (last_rel.number_sequency + 1) if last_rel else 1
            release = Release.objects.create(
                release_code=Release.generate_code(year, rel_seq),
                year=year, number_sequency=rel_seq
            )
        else:
            release = get_object_or_404(Release, id=release_id)
            if release.ecs.count() >= Release.MAX_ECS_PER_RELEASE:
                messages.error(request, f'Release {release.release_code} nakonu tiha ({Release.MAX_ECS_PER_RELEASE}/{Release.MAX_ECS_PER_RELEASE}). Hili release seluk ka kria release foun.')
                return redirect('ec_create')

        reviewer = get_object_or_404(User, id=reviewer_id)

        ec = ECS.objects.create(
            esc_code=esc_code, year=year, number_sequenci=seq,
            cr_rt_me_reference=ref, description=desc,
            id_release=release, id_solicitante=request.user,
            cd_responsavel_id=reviewer
        )

        if file:
            DocumentVersion.objects.create(
                ec=ec, uploaded_by=request.user,
                version_number='v1.0', file_path=file,
                change_reason='Versaun inisiál'
            )

        log_action(ec, request.user, 'Kria EC', f'Versaun v1.0')
        log_action(ec, request.user, f'Atribui ba {reviewer.get_full_name()}')
        messages.success(request, f'EC {esc_code} kria ho susesu.')
        return redirect('ec_detail', esc_code=esc_code)

    releases = Release.objects.filter(production_go_live_date__isnull=True)
    reviewers = User.objects.filter(role='Reviewer', active=True)
    current_year = date.today().year
    return render(request, 'backlog/ec_create.html', {
        'releases': releases, 'reviewers': reviewers,
        'max_ecs': Release.MAX_ECS_PER_RELEASE,
        'current_year': current_year,
    })


@login_required
def ec_detail(request, esc_code):
    ec = get_object_or_404(ECS, esc_code=esc_code)
    versions = ec.versions.all()
    # DES: hatudu de'it versaun ikus (subar versaun reject / v1.0 tuan)
    if request.user.role == 'DES':
        versions = versions[:1]
    history = ec.audit_logs.all()
    reviewers = User.objects.filter(role='Reviewer', active=True)
    return render(request, 'backlog/ec_detail.html', {
        'ec': ec, 'versions': versions, 'history': history,
        'role': request.user.role, 'reviewers': reviewers,
    })


@login_required
def ec_reassign(request, esc_code):
    # Solicitante (pemilik) no Admin bele troka reviewer
    ec = get_object_or_404(ECS, esc_code=esc_code)
    if request.user.role not in ('Solicitante', 'Admin'):
        messages.error(request, 'Ita la iha permisaun atu troka reviewer.')
        return redirect('ec_detail', esc_code=esc_code)
    if request.user.role == 'Solicitante' and ec.id_solicitante != request.user:
        messages.error(request, 'So solicitante nain mak bele troka reviewer.')
        return redirect('ec_detail', esc_code=esc_code)
    if ec.status not in ('Em_Validasaun', 'Rejeitadu'):
        messages.error(request, 'EC ho estado neé la bele troka reviewer.')
        return redirect('ec_detail', esc_code=esc_code)
    if request.method == 'POST':
        new_id = request.POST.get('reviewer')
        new_rev = get_object_or_404(User, id=new_id, role='Reviewer', active=True)
        old = ec.cd_responsavel_id.get_full_name() if ec.cd_responsavel_id else '—'
        ec.cd_responsavel_id = new_rev
        # Se EC rejeitadu no troka reviewer, loke fali ba validasaun
        if ec.status == 'Rejeitadu':
            ec.status = 'Em_Validasaun'
            ec.rejection_comment = ''
        ec.save()
        log_action(ec, request.user, f'Troka reviewer: {old} → {new_rev.get_full_name()}')
        messages.success(request, f'Reviewer troka ba {new_rev.get_full_name()} ho susesu.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def ec_approve(request, esc_code):
    if request.user.role != 'Reviewer':
        return redirect('dashboard')
    ec = get_object_or_404(ECS, esc_code=esc_code)
    ec.status = 'Aprovadu'
    ec.save()
    log_action(ec, request.user, 'Aprovadu')
    messages.success(request, f'EC {esc_code} aprovadu.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def ec_reject(request, esc_code):
    if request.user.role != 'Reviewer':
        return redirect('dashboard')
    ec = get_object_or_404(ECS, esc_code=esc_code)
    comment = request.POST.get('rejection_comment', '')
    if not comment:
        messages.error(request, 'Komentariu obrigatóriu.')
        return redirect('ec_detail', esc_code=esc_code)
    ec.status = 'Rejeitadu'
    ec.rejection_comment = comment
    ec.save()
    log_action(ec, request.user, 'Rejeitadu', comment)
    messages.error(request, f'EC {esc_code} rejeitadu.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def ec_revise(request, esc_code):
    if request.user.role != 'Solicitante':
        return redirect('dashboard')
    ec = get_object_or_404(ECS, esc_code=esc_code, status='Rejeitadu')
    file = request.FILES.get('document')
    if not file:
        messages.error(request, 'Upload ficheiru foun.')
        return redirect('ec_detail', esc_code=esc_code)

    last_ver = ec.versions.first()
    num = float(last_ver.version_number.replace('v','')) + 0.1 if last_ver else 1.0
    new_ver = f"v{num:.1f}"

    DocumentVersion.objects.create(
        ec=ec, uploaded_by=request.user,
        version_number=new_ver, file_path=file,
        change_reason='Korreksaun pos-rejeisaun'
    )
    ec.status = 'Em_Validasaun'
    ec.rejection_comment = ''
    ec.save()
    log_action(ec, request.user, f'Upload versaun foun {new_ver}')
    log_action(ec, request.user, f'Atribui fali ba {ec.cd_responsavel_id.get_full_name()}')
    messages.success(request, f'Versaun {new_ver} upload ho susesu.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def ec_cancel(request, esc_code):
    # Fitur Cancela dinonaktifkan — Admin tidak boleh cancel.
    messages.error(request, 'Fungsaun Cancela hasai tiha — Admin labele kansela EC.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def ec_set_prd(request, esc_code):
    if request.user.role != 'DES':
        return redirect('dashboard')
    ec = get_object_or_404(ECS, esc_code=esc_code)
    prd_date = request.POST.get('production_go_live_date')
    ec.status = 'Fechadu'
    ec.save()
    # Release TIDAK otomatis ketutup saat 1 EC fecha.
    # 1 release max 10 EC, solicitante bebas pilih release aberta mana saja,
    # tidak harus nunggu 001 penuh dulu. Release ketutup hanya kalau penuh 10/10
    # (disabled di dropdown) atau Go-Live manual.
    log_action(ec, request.user, f'Tama Produsaun ({prd_date})')
    messages.success(request, f'EC {esc_code} fechadu.')
    return redirect('ec_detail', esc_code=esc_code)


@login_required
def release_list(request):
    from datetime import date as d
    releases = Release.objects.all()
    current_year = d.today().year
    return render(request, 'backlog/release_list.html', {
        'releases': releases,
        'max_ecs': Release.MAX_ECS_PER_RELEASE,
        'current_year': current_year,
    })


@login_required
def release_detail(request, release_code):
    release = get_object_or_404(Release, release_code=release_code)
    ecs = release.ecs.select_related('id_solicitante', 'cd_responsavel_id', 'id_release').all()
    ecs = ecs.order_by('-year', '-number_sequenci')
    return render(request, 'backlog/release_detail.html', {
        'release': release, 'ecs': ecs,
        'role': request.user.role,
        'max_ecs': Release.MAX_ECS_PER_RELEASE,
    })


@login_required
def user_list(request):
    if request.user.role != 'Admin':
        return redirect('dashboard')
    if request.method == 'POST':
        action = request.POST.get('action', 'toggle')

        if action == 'create':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            role = request.POST.get('role', 'Solicitante')
            password = request.POST.get('password', '').strip()
            if not username or not password or not first_name:
                messages.error(request, 'Username, Naran, no Password obrigatóriu.')
            elif User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" uza tiha ona.')
            else:
                u = User(username=username, first_name=first_name, last_name=last_name,
                         email=email, role=role, active=True)
                u.set_password(password)
                if role == 'Admin':
                    u.is_staff = True
                u.save()
                messages.success(request, f'Utilizadór {username} ({first_name} {last_name}) kria ho susesu.')
            return redirect('user_list')

        elif action == 'update':
            uid = request.POST.get('user_id')
            u = get_object_or_404(User, id=uid)
            u.first_name = request.POST.get('first_name', '').strip()
            u.last_name = request.POST.get('last_name', '').strip()
            u.email = request.POST.get('email', '').strip()
            u.role = request.POST.get('role', u.role)
            new_pw = request.POST.get('password', '').strip()
            if new_pw:
                u.set_password(new_pw)
            if u.role == 'Admin':
                u.is_staff = True
            u.save()
            messages.success(request, f'Dadus {u.username} atualiza ho susesu.')
            return redirect('user_list')

        elif action == 'delete':
            uid = request.POST.get('user_id')
            u = get_object_or_404(User, id=uid)
            if u == request.user:
                messages.error(request, 'Labele hapus konta rasik.')
                return redirect('user_list')
            try:
                username = u.username
                u.delete()
                messages.success(request, f'Utilizadór {username} hapus ho susesu.')
            except Exception:
                messages.error(request, f'Utilizadór {u.username} iha EC / istoria, labele hapus. Dezativa deit.')
            return redirect('user_list')

        else:  # toggle
            uid = request.POST.get('user_id')
            u = get_object_or_404(User, id=uid)
            u.active = not u.active
            u.save()
            messages.success(request, f'Utilizadór {u.username} {"ativu" if u.active else "dezativu"}.')
            return redirect('user_list')

    users = User.objects.all().order_by('role', 'username')
    return render(request, 'backlog/user_list.html', {'users': users, 'roles': User.ROLE_CHOICES})