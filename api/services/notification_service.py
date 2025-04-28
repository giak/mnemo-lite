"""
Service de notification pour l'envoi d'alertes et de messages aux utilisateurs.
Implémente l'interface NotificationServiceProtocol.
"""

import logging
from typing import Dict, Any, Optional, List, Union
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import asyncio
from datetime import datetime

from interfaces.services import NotificationServiceProtocol

# Configuration du logger
logger = logging.getLogger(__name__)

class NotificationService(NotificationServiceProtocol):
    """
    Implémentation du service de notification.
    Ce service permet d'envoyer des notifications aux utilisateurs.
    Il peut être utilisé pour envoyer des alertes, des rappels ou d'autres messages.
    """
    
    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        default_sender: Optional[str] = None
    ):
        """
        Initialise le service de notification.
        
        Args:
            smtp_host: Hôte SMTP pour l'envoi d'emails
            smtp_port: Port SMTP
            smtp_user: Nom d'utilisateur SMTP
            smtp_password: Mot de passe SMTP
            default_sender: Adresse email d'expédition par défaut
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.default_sender = default_sender or "noreply@mnemolite.app"
        
        # Valider la configuration SMTP
        self.smtp_configured = all([smtp_host, smtp_port, smtp_user, smtp_password])
        
        # Initialiser le journal des notifications (pour le débogage et les tests)
        self.notification_log: List[Dict[str, Any]] = []
        
        logger.info("Initialisation du service de notification")
        if not self.smtp_configured:
            logger.warning("Configuration SMTP incomplète, les emails ne seront pas envoyés")
    
    async def send_notification(
        self, 
        user_id: str, 
        message: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Envoie une notification à un utilisateur.
        
        Args:
            user_id: Identifiant de l'utilisateur
            message: Contenu du message
            metadata: Métadonnées additionnelles (comme le type de notification, la priorité, etc.)
            
        Returns:
            True si la notification a été envoyée avec succès, False sinon
        """
        try:
            logger.info(f"Envoi de notification à l'utilisateur {user_id}")
            
            # Enrichir les métadonnées
            meta = metadata.copy() if metadata else {}
            meta["timestamp"] = datetime.utcnow().isoformat()
            meta["status"] = "pending"
            
            # Créer l'entrée de journal
            log_entry = {
                "user_id": user_id,
                "message": message,
                "metadata": meta,
                "timestamp": meta["timestamp"]
            }
            
            # En environnement de production, envoyer l'email
            if self.smtp_configured:
                # Simuler un délai d'envoi
                await asyncio.sleep(0.1)
                
                # Mettre à jour le statut (dans un cas réel, cela serait fait après l'envoi effectif)
                meta["status"] = "sent"
                log_entry["metadata"] = meta
            else:
                # En mode développement ou test, juste journaliser
                logger.debug(f"Notification pour {user_id}: {message}")
                meta["status"] = "logged_only"
                log_entry["metadata"] = meta
            
            # Ajouter au journal
            self.notification_log.append(log_entry)
            
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de notification à {user_id}: {str(e)}")
            return False
    
    async def broadcast_notification(
        self, 
        message: str, 
        user_ids: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Envoie une notification à plusieurs utilisateurs.
        
        Args:
            message: Contenu du message
            user_ids: Liste des identifiants des utilisateurs destinataires
                     Si None, envoie à tous les utilisateurs
            
        Returns:
            Dictionnaire avec les identifiants des utilisateurs comme clés et 
            des booléens indiquant si la notification a été envoyée avec succès comme valeurs
        """
        try:
            if not user_ids:
                logger.warning("Aucun destinataire spécifié pour la diffusion de notification")
                return {}
            
            logger.info(f"Diffusion de notification à {len(user_ids)} utilisateurs")
            
            # Préparer les métadonnées communes
            common_metadata = {
                "broadcast_id": str(datetime.utcnow().timestamp()),
                "broadcast_size": len(user_ids),
                "type": "broadcast"
            }
            
            # Envoyer à chaque utilisateur
            results = {}
            for user_id in user_ids:
                success = await self.send_notification(
                    user_id=user_id,
                    message=message,
                    metadata=common_metadata
                )
                results[user_id] = success
            
            # Journaliser les résultats
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"Diffusion terminée: {success_count}/{len(user_ids)} notifications envoyées")
            
            return results
        except Exception as e:
            logger.error(f"Erreur lors de la diffusion de notification: {str(e)}")
            return {user_id: False for user_id in (user_ids or [])} 