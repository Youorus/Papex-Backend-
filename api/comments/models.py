from django.db import models
from django.utils.translation import gettext_lazy as _


class Comment(models.Model):
    """
    Modèle représentant un commentaire lié à un lead.
    Attributs :
        - lead : ForeignKey vers Lead.
        - author : ForeignKey vers User.
        - content : texte du commentaire.
        - created_at / updated_at : dates automatiques.
    """

    lead = models.ForeignKey(
        "leads.Lead",
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("Lead associé"),
    )
    author = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, verbose_name=_("Auteur")
    )
    content = models.TextField(_("Contenu"))
    created_at = models.DateTimeField(_("Date de création"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Date de modification"), auto_now=True)

    class Meta:
        verbose_name = _("Commentaire")
        verbose_name_plural = _("Commentaires")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Commentaire #{self.id} par {self.author.get_full_name()}"
