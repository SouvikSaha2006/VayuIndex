import {
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  inject,
  AfterViewChecked,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { VayuService } from '../services/vayu.service';
import { ChatMessage, ChatbotResponse } from '../models/vayu.model';

@Component({
  selector: 'app-vayumitra-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './vayumitra-chat.component.html',
  styleUrl: './vayumitra-chat.component.scss',
})
export class VayuMitraChatComponent implements OnInit, AfterViewChecked {
  private readonly vayuService = inject(VayuService);

  @ViewChild('scrollContainer') private scrollContainer?: ElementRef;
  @ViewChild('chatInput') private chatInput?: ElementRef<HTMLInputElement>;

  isOpen: boolean = false;
  isLoading: boolean = false;
  inputText: string = '';
  shouldScroll: boolean = false;

  messages: ChatMessage[] = [];
  suggestedChips: string[] = [
    'DEL to BOM',
    'Current CPI Index',
    'Govt Helplines',
    'BOM to BLR',
  ];

  ngOnInit(): void {
    this.addWelcomeMessage();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.scrollToBottom();
      this.shouldScroll = false;
    }
  }

  toggleChat(): void {
    this.isOpen = !this.isOpen;
    if (this.isOpen) {
      this.shouldScroll = true;
      setTimeout(() => {
        this.chatInput?.nativeElement.focus();
      }, 200);
    }
  }

  closeChat(): void {
    this.isOpen = false;
  }

  resetChat(): void {
    this.messages = [];
    this.addWelcomeMessage();
    this.suggestedChips = [
      'DEL to BOM',
      'Current CPI Index',
      'Govt Helplines',
      'BOM to BLR',
    ];
    this.shouldScroll = true;
  }

  private addWelcomeMessage(): void {
    this.messages.push({
      id: 'msg-welcome',
      sender: 'bot',
      text:
        'Namaste! 🙏 I am **VayuMitra** (वायु मित्र), your official AI Assistant for the **VayuIndex** Airfare Volatility & CPI Portal.\n\n' +
        'You can ask me:\n' +
        '• ✈️ **"DEL to BOM"** for live corridor fares & baseline benchmark\n' +
        '• 📊 **"Current CPI Index"** for national inflation metrics\n' +
        '• 🏛️ **"Helplines"** for AirSewa & DGCA passenger grievance contacts',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });
  }

  onChipClick(chip: string): void {
    this.sendMessage(chip);
  }

  sendMessage(overrideText?: string): void {
    const textToSend = (overrideText ?? this.inputText).trim();
    if (!textToSend || this.isLoading) {
      return;
    }

    // Add user message
    const userMsg: ChatMessage = {
      id: 'user-' + Date.now(),
      sender: 'user',
      text: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    this.messages.push(userMsg);
    this.inputText = '';
    this.isLoading = true;
    this.shouldScroll = true;

    // Call API
    this.vayuService.sendChatMessage(textToSend).subscribe({
      next: (res: ChatbotResponse) => {
        const botMsg: ChatMessage = {
          id: 'bot-' + Date.now(),
          sender: 'bot',
          text: res.reply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        this.messages.push(botMsg);
        if (res.suggested_chips && res.suggested_chips.length > 0) {
          this.suggestedChips = res.suggested_chips;
        }
        this.isLoading = false;
        this.shouldScroll = true;
      },
      error: () => {
        const errorMsg: ChatMessage = {
          id: 'err-' + Date.now(),
          sender: 'bot',
          text: '⚠️ An error occurred while retrieving official statistics. Please check your network or try again.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        this.messages.push(errorMsg);
        this.isLoading = false;
        this.shouldScroll = true;
      },
    });
  }

  private scrollToBottom(): void {
    try {
      if (this.scrollContainer) {
        this.scrollContainer.nativeElement.scrollTop =
          this.scrollContainer.nativeElement.scrollHeight;
      }
    } catch {
      // Ignore scroll errors
    }
  }

  /**
   * Basic markdown parsing for safe display of bold, italics, bullets and line breaks.
   */
  formatMessage(rawText: string): string {
    if (!rawText) return '';
    let formatted = rawText
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Bold: **text** or *text*
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*(.*?)\*/g, '<strong>$1</strong>');

    // Code: `code`
    formatted = formatted.replace(/`(.*?)`/g, '<code>$1</code>');

    // Line breaks
    formatted = formatted.replace(/\n/g, '<br/>');

    return formatted;
  }
}
