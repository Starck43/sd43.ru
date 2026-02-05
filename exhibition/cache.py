from exhibition.services import delete_cached_fragment
from exhibition.models import Portfolio


def invalidate_portfolio_cache(portfolio: "Portfolio"):
    owner = portfolio.owner

    delete_cached_fragment('portfolio_list', owner.slug, portfolio.project_id, True)
    delete_cached_fragment('portfolio_list', owner.slug, portfolio.project_id, False)
    delete_cached_fragment('portfolio_slider', owner.slug, portfolio.project_id)
    delete_cached_fragment('participant_detail', owner.id)

    # По номинациям
    for nomination in portfolio.nominations.select_related('category').all():
        if nomination.category:
            delete_cached_fragment('projects_list', nomination.category.slug)
            delete_cached_fragment('sidebar', nomination.category.slug)

    # Победы
    from .models import Winners
    victories = Winners.objects.filter(portfolio=portfolio).select_related('exhibition', 'nomination')

    for victory in victories:
        delete_cached_fragment(
            'portfolio_list',
            victory.exhibition.slug,
            victory.nomination.slug,
            True
        )
        delete_cached_fragment(
            'portfolio_list',
            victory.exhibition.slug,
            victory.nomination.slug,
            False
        )
        delete_cached_fragment(
            'portfolio_slider',
            victory.exhibition.slug,
            victory.nomination.slug
        )
